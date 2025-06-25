import sys
import os
import json
from lxml import etree
import logging

# --- Setup Logging ---
# Configures logging to write to a file, overwriting it on each run.
logging.basicConfig(filename='map_porter.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filemode='w')

# --- Globals for reporting ---
UNHANDLED_COMPONENTS = set()

# --- Path Helpers ---
def get_unreal_asset_path(nif_path_rel, gsa_dir):
    """
    Converts a relative NIF path from the GSA file to a standardized
    Unreal Engine content browser path. It handles various path formats,
    including those with '..', by resolving the path against the GSA file's
    directory and finding the root 'Data' folder.
    e.g., ('.\\..\\..\\00_Object\\model.nif', 'Client/Data/3_World/99_Tutorial') -> '/Game/00_Object/model'
    """
    if not nif_path_rel or not isinstance(nif_path_rel, str):
        logging.warning(f"Invalid nif_path_rel provided: {nif_path_rel}")
        return None

    # Create a full, absolute-like path from the file's directory, then normalize it
    full_nif_path = os.path.join(gsa_dir, nif_path_rel)
    normalized_path = os.path.normpath(full_nif_path)

    # The game's assets are in subdirectories of 'Data'. We find 'Data' in the path
    # to correctly construct the '/Game/...' path for Unreal.
    path_parts = normalized_path.replace('\\', '/').split('/')
    
    try:
        # Find the 'Data' folder and take everything after it
        data_index = path_parts.index('Data')
        relative_to_data = path_parts[data_index + 1:]
        
        # Reconstruct the path and remove the .nif extension
        clean_path = '/'.join(relative_to_data)
        if clean_path.lower().endswith('.nif'):
            clean_path = clean_path[:-4]
            
        return os.path.join('/Game', clean_path).replace('\\', '/')
        
    except ValueError:
        # If 'Data' is not in the path, our assumption is wrong for this asset.
        logging.warning(f"Could not find 'Data' root in path: {normalized_path}")
        return None


# --- Component Parsers ---
def parse_transform(component):
    """Parses translation, rotation, and scale from a NiTransformationComponent element."""
    transform = {}
    
    translation_prop = component.find("PROPERTY[@Name='Translation']")
    if translation_prop is not None and translation_prop.text:
        try:
            transform['translation'] = [float(v.strip()) for v in translation_prop.text.split(',')]
        except (ValueError, TypeError) as e:
            logging.warning(f"Could not parse translation: {translation_prop.text}. Error: {e}")

    rotation_matrix = component.find("PROPERTY[@Name='Rotation']")
    if rotation_matrix is not None:
        rows = rotation_matrix.findall('ROW')
        if rows:
            try:
                matrix = []
                for row in rows:
                    if row.text:
                        matrix.append([float(v.strip()) for v in row.text.split(',')])
                if matrix:
                    transform['rotation'] = matrix
            except (ValueError, TypeError) as e:
                logging.warning(f"Could not parse rotation matrix. Error: {e}")

    scale_prop = component.find("PROPERTY[@Name='Scale']")
    if scale_prop is not None and scale_prop.text:
        try:
            transform['scale'] = float(scale_prop.text)
        except (ValueError, TypeError) as e:
            logging.warning(f"Could not parse scale: {scale_prop.text}. Error: {e}")
        
    return transform

def parse_light(component):
    """Parses all properties from a NiLightComponent into a dictionary."""
    light_props = {}
    for prop in component.findall('PROPERTY'):
        prop_name = prop.get('Name')
        prop_class = prop.get('Class')
        prop_text = prop.text.strip() if prop.text else ''

        if not prop_name:
            continue
            
        key_name = prop_name.lower().replace(' ', '_').replace('(', '').replace(')', '')

        if prop_class == "Entity Pointer":
            affected_entities = []
            for item in prop.findall('ITEM'):
                ref_id = item.get('RefLinkID')
                if ref_id:
                    affected_entities.append(ref_id)
            light_props[key_name] = affected_entities
        elif prop_class == "Color (RGB)":
             try:
                light_props[key_name] = [float(v.strip()) for v in prop_text.split(',')]
             except (ValueError, TypeError):
                logging.warning(f"Could not parse RGB color: {prop_text}")
        elif prop_class == "Float":
            try:
                light_props[key_name] = float(prop_text)
            except (ValueError, TypeError):
                logging.warning(f"Could not parse float: {prop_text}")
        else: # String, etc.
            light_props[key_name] = prop_text
            
    return light_props

# --- Core Logic ---
def get_component_data(component_ref, components_map, templates_map, gsa_dir):
    """
    Recursively gathers data from a component, following MasterLinkID references
    to templates. Properties from the instance component override the template's.
    """
    data = {}
    comp_link_id = component_ref.get('RefLinkID')
    
    if not comp_link_id or comp_link_id not in components_map:
        return None

    component = components_map[comp_link_id]
    comp_class = component.get('Class')
    comp_name = component.get('Name')
    
    master_link_id = component.get('MasterLinkID')
    if master_link_id and master_link_id in components_map:
        master_ref = etree.Element("DUMMY")
        master_ref.set('RefLinkID', master_link_id)
        data.update(get_component_data(master_ref, components_map, templates_map, gsa_dir))

    data['link_id'] = comp_link_id
    data['class'] = comp_class
    data['name'] = comp_name

    if comp_class == 'NiTransformationComponent':
        data.update(parse_transform(component))
    elif comp_class == 'NiSceneGraphComponent':
        sg_prop = component.find("PROPERTY[@Name='Scene Root']")
        if sg_prop is None:
            sg_prop = component.find("PROPERTY[@Name='NIF File Path']")
        if sg_prop is not None and sg_prop.text:
            nif_path_rel = sg_prop.text.strip()
            data['unreal_path'] = get_unreal_asset_path(nif_path_rel, gsa_dir)
            data['nif_path_rel'] = nif_path_rel
    elif comp_class == 'NiLightComponent':
        data.update(parse_light(component))
    elif comp_class not in ['NiCameraComponent', 'NiGeneralComponent', 'NiCollisionComponent']:
        UNHANDLED_COMPONENTS.add(f"{comp_class}::{comp_name}")
        
    return data

def get_entity_data(entity, components_map, templates_map, gsa_dir):
    """Gathers data for a single entity instance, resolving its template and components."""
    master_link = entity.get('MasterLinkID')
    if not master_link or master_link not in templates_map:
        return None
        
    template_entity = templates_map[master_link]
    
    entity_data = {
        'name': entity.get('Name'),
        'class': entity.get('Class'),
        'type': entity.get('Type'),
        'template_id': template_entity.get('LinkID'),
        'instance_id': entity.get('LinkID'),
        'components': []
    }

    template_components = {}
    for comp_ref in template_entity.findall('COMPONENT'):
        comp_data = get_component_data(comp_ref, components_map, templates_map, gsa_dir)
        if comp_data:
            template_components[comp_data['name']] = comp_data

    instance_components = {}
    for comp_ref in entity.findall('COMPONENT'):
        comp_data = get_component_data(comp_ref, components_map, templates_map, gsa_dir)
        if comp_data:
            instance_components[comp_data['name']] = comp_data
            
    final_components = template_components.copy()
    final_components.update(instance_components)
    
    entity_data['components'] = list(final_components.values())
    
    return entity_data

def main():
    """Main execution function."""
    if len(sys.argv) != 4:
        print("Usage: python map_porter.py <path_to_gsa_file> <source_root_dir> <target_root_dir>")
        sys.exit(1)

    gsa_path = sys.argv[1]
    source_root = sys.argv[2]
    target_root = sys.argv[3]
    
    if not os.path.exists(gsa_path):
        logging.error(f"Input file not found at '{gsa_path}'")
        print(f"Error: Input file not found at '{gsa_path}'")
        sys.exit(1)
        
    # --- Calculate Output Path ---
    try:
        full_gsa_path = os.path.abspath(gsa_path)
        full_source_root = os.path.abspath(source_root)
        
        # Get the path of the GSA file relative to the source root
        relative_path = os.path.relpath(full_gsa_path, full_source_root)
        
        # Change the extension to .json
        path_without_ext, _ = os.path.splitext(relative_path)
        new_relative_path = path_without_ext + ".json"
        
        # Create the final output path in the target directory
        output_path = os.path.join(target_root, new_relative_path)
        
        # Create the directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

    except Exception as e:
        logging.error(f"Error calculating output path: {e}")
        print(f"Error calculating output path: {e}")
        sys.exit(1)
        
    logging.info(f"Processing GSA file: {gsa_path}")
    gsa_dir = os.path.dirname(gsa_path)
    
    components_map = {}
    templates_map = {}
    
    try:
        # --- First Pass: Map all components and templates by LinkID for efficient lookup ---
        logging.info("Starting first pass: mapping components and templates...")
        context = etree.iterparse(gsa_path, events=('end',), tag=('ENTITY', 'COMPONENT'))
        for _, element in context:
            if element.tag == 'COMPONENT':
                link_id = element.get('LinkID')
                if link_id:
                    components_map[link_id] = element
            elif element.tag == 'ENTITY':
                if element.get('MasterLinkID') is None: # This identifies a template
                    link_id = element.get('LinkID')
                    if link_id:
                        templates_map[link_id] = element
            # Free memory by clearing the element and its predecessors
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
        del context
        logging.info(f"First pass complete. Found {len(components_map)} components and {len(templates_map)} templates.")

        # --- Second Pass: Process only instance entities and build scene data ---
        logging.info("Starting second pass: processing instance entities...")
        scene_data = {'entities': []}
        context = etree.iterparse(gsa_path, events=('end',), tag='ENTITY')
        for _, entity in context:
            if entity.get('MasterLinkID') is not None: # This identifies an instance
                entity_data = get_entity_data(entity, components_map, templates_map, gsa_dir)
                if entity_data:
                    scene_data['entities'].append(entity_data)
            entity.clear()
            while entity.getprevious() is not None:
                del entity.getparent()[0]
        del context
        logging.info("Second pass complete. Processing complete.")
        
        # --- Write final output ---
        logging.info(f"Writing scene data to {output_path}")
        with open(output_path, 'w') as f:
            json.dump(scene_data, f, indent=4)
        
        if UNHANDLED_COMPONENTS:
            logging.warning("--- Unhandled Components ---")
            for comp in sorted(list(UNHANDLED_COMPONENTS)):
                logging.warning(comp)
        
        print(f"Successfully parsed GSA file and created {output_path}")

    except etree.XMLSyntaxError as e:
        logging.error(f"XML Syntax Error in {gsa_path}: {e}")
        print(f"Error: XML Syntax Error in '{gsa_path}'. See log for details.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        print("An unexpected error occurred. Please check the log file 'map_porter.log' for details.")

if __name__ == '__main__':
    main()