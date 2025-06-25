import unreal
import json
import os
import math
import time

# Configuration - Adjust these settings as needed
JSON_FILE_PATH = ""  # Will be set via command line argument
MAP_NAME = "DragonicaMap"  # Will be appended with the JSON filename
SCALE_FACTOR = 0.02  # Initial guess based on other Korean MMOs (adjust after testing)
ORGANIZE_BY_TYPE = True  # Whether to organize objects by type into folders
SHOW_PROGRESS_BAR = True  # Whether to show a progress bar during processing

# Color coding for different entity types (RGB values)
TYPE_COLORS = {
    "Object": (0.75, 0.75, 0.75),  # Light gray for generic objects
    "Telejump": (0.0, 1.0, 0.5),  # Bright green for teleport points
    "PhysX": (1.0, 0.5, 0.0),  # Orange for physics objects
    "MainCamera": (0.0, 0.5, 1.0),  # Blue for cameras
    "Light": (1.0, 1.0, 0.0),  # Yellow for lights
    "GlowMap": (1.0, 0.0, 1.0),  # Purple for glow maps
    "SharedStream": (0.0, 1.0, 1.0),  # Cyan for streaming volumes
    "Default": (0.5, 0.5, 0.5)  # Gray for unknown types
}

# Proxy mesh selection based on entity type
TYPE_MESHES = {
    "Object": "/Engine/BasicShapes/Cube",
    "Telejump": "/Engine/BasicShapes/Cylinder",
    "PhysX": "/Engine/BasicShapes/Sphere",
    "MainCamera": "/Engine/EditorMeshes/Camera/SM_CineCam",
    "Light": "/Engine/EditorMeshes/Lighting/LightIcon_PointLight",
    "GlowMap": "/Engine/BasicShapes/Plane",
    "SharedStream": "/Engine/BasicShapes/Plane",
    "Default": "/Engine/BasicShapes/Cube"
}

def show_message(message):
    """Display a message in the Unreal Editor's log"""
    unreal.log(message)
    print(message)  # Also print to Python console

def show_progress_bar(current, total, prefix='Progress:', suffix='Complete', length=50):
    """Show a text-based progress bar"""
    if not SHOW_PROGRESS_BAR:
        return
        
    percent = float(current) / float(total)
    filled_length = int(length * percent)
    bar = '█' * filled_length + '-' * (length - filled_length)
    progress_text = f'\r{prefix} |{bar}| {percent:.1%} {suffix}'
    print(progress_text, end='\r')
    
    # Print a new line when complete
    if current == total:
        print()

def test_scale_factors(json_data):
    """
    Create a test level with different scale factors to determine the correct one
    Returns the created level path
    """
    show_message("Creating scale test level...")
    
    # Get the editor subsystem
    editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    
    # Create a new level for testing
    test_level_path = '/Game/Maps/DragonicaScaleTest'
    editor_subsystem.new_level(test_level_path)
    
    # Find a representative object (like a building or character)
    test_entities = []
    entity_count = min(len(json_data.get('entities', [])), 5)  # Test with up to 5 entities
    
    # Try to find entities with specific keywords first
    keywords = ['building', 'character', 'house', 'tree', 'door']
    
    for keyword in keywords:
        if len(test_entities) >= entity_count:
            break
            
        for entity in json_data.get('entities', []):
            entity_name = entity.get('name', '').lower()
            if keyword in entity_name and entity not in test_entities:
                test_entities.append(entity)
                if len(test_entities) >= entity_count:
                    break
    
    # If we didn't find enough keyword matches, add some random entities
    if len(test_entities) < entity_count:
        for entity in json_data.get('entities', []):
            if entity not in test_entities:
                test_entities.append(entity)
                if len(test_entities) >= entity_count:
                    break
    
    # Test different scale factors
    scale_factors = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    
    # Create a text explaining the test
    info_text = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.TextRenderActor, 
        unreal.Vector(0, 0, 200),
        unreal.Rotator(0, 0, 0)
    )
    info_text.text_render.set_text(
        "SCALE TEST LEVEL\n" +
        "Each row shows the same objects at different scale factors\n" +
        "Choose the scale that looks most natural for your game"
    )
    info_text.text_render.set_text_render_color(unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    info_text.text_render.horizontal_alignment = unreal.TextRenderHorizontalAlignment.CENTER
    info_text.text_render.set_world_size(50)  # Make text larger
    
    # For each test entity
    for entity_index, entity in enumerate(test_entities):
        # Extract transform data
        transform_data = None
        entity_type = entity.get('type', 'Object')
        entity_name = entity.get('name', 'Unknown')
        
        for component in entity.get('components', []):
            if component.get('class') == 'NiTransformationComponent':
                transform_data = component
                break
        
        if transform_data:
            translation = transform_data.get('translation', [0, 0, 0])
            rotation_matrix = transform_data.get('rotation')
            scale_value = transform_data.get('scale', 1.0)
            
            # Create a label for this entity
            entity_label = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.TextRenderActor, 
                unreal.Vector(-300, entity_index * 1000, 0),
                unreal.Rotator(0, 0, 0)
            )
            entity_label.text_render.set_text(f"Entity: {entity_name} ({entity_type})")
            entity_label.text_render.set_text_render_color(unreal.LinearColor(1.0, 1.0, 0.0, 1.0))
            
            # Test each scale factor for this entity
            for i, factor in enumerate(scale_factors):
                # Apply scaling factor
                scaled_translation = [t * factor for t in translation]
                
                # Create location vector - offset each test object along Y axis
                location = unreal.Vector(
                    i * 300,  # X position based on scale factor
                    entity_index * 1000,  # Y position based on entity
                    scaled_translation[2]  # Z from the entity data
                )
                
                # Create a test object
                actor = editor_subsystem.spawn_actor_from_class(
                    unreal.StaticMeshActor, 
                    location, 
                    unreal.Rotator(0, 0, 0)
                )
                
                # Set up the test object
                actor.set_actor_label(f"ScaleTest_{entity_index}_{factor}")
                
                # Load an appropriate mesh
                mesh_path = TYPE_MESHES.get(entity_type, TYPE_MESHES["Default"])
                mesh = unreal.load_asset(mesh_path)
                if mesh:
                    actor.static_mesh_component.set_static_mesh(mesh)
                
                # Apply color based on entity type
                color = TYPE_COLORS.get(entity_type, TYPE_COLORS["Default"])
                material_instance = actor.static_mesh_component.create_and_set_material_instance_dynamic(0)
                if material_instance:
                    material_instance.set_vector_parameter_value(
                        'Color', 
                        unreal.LinearColor(color[0], color[1], color[2], 1.0)
                    )
                
                # Create a text render component to show the scale factor
                text = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.TextRenderActor, 
                    unreal.Vector(location.x, location.y, location.z + 100),
                    unreal.Rotator(0, 0, 0)
                )
                text.text_render.set_text(f"Scale: {factor}")
                text.text_render.set_text_render_color(unreal.LinearColor(1.0, 1.0, 0.0, 1.0))
    
    # Save the level
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    show_message(f"Created scale test level at {test_level_path}")
    show_message("Examine each object to determine correct scale factor")
    show_message("Then update the SCALE_FACTOR in this script accordingly")
    
    return test_level_path

def matrix_to_quaternion(matrix):
    """
    Convert a Gamebryo 3×3 rotation matrix to an Unreal quaternion
    Handles coordinate system differences
    """
    if not matrix or len(matrix) < 3 or len(matrix[0]) < 3:
        return unreal.Quat(0, 0, 0, 1)  # Identity quaternion
    
    try:
        # First, we need to adapt for coordinate system differences
        # Gamebryo: Y-up, Unreal: Z-up
        adapted_matrix = [
            [matrix[0][0], matrix[0][2], -matrix[0][1]],
            [matrix[2][0], matrix[2][2], -matrix[2][1]],
            [-matrix[1][0], -matrix[1][2], matrix[1][1]]
        ]
        
        # Then convert to quaternion using standard algorithm
        trace = adapted_matrix[0][0] + adapted_matrix[1][1] + adapted_matrix[2][2]
        
        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (adapted_matrix[2][1] - adapted_matrix[1][2]) * s
            y = (adapted_matrix[0][2] - adapted_matrix[2][0]) * s
            z = (adapted_matrix[1][0] - adapted_matrix[0][1]) * s
        else:
            if adapted_matrix[0][0] > adapted_matrix[1][1] and adapted_matrix[0][0] > adapted_matrix[2][2]:
                s = 2.0 * math.sqrt(1.0 + adapted_matrix[0][0] - adapted_matrix[1][1] - adapted_matrix[2][2])
                w = (adapted_matrix[2][1] - adapted_matrix[1][2]) / s
                x = 0.25 * s
                y = (adapted_matrix[0][1] + adapted_matrix[1][0]) / s
                z = (adapted_matrix[0][2] + adapted_matrix[2][0]) / s
            elif adapted_matrix[1][1] > adapted_matrix[2][2]:
                s = 2.0 * math.sqrt(1.0 + adapted_matrix[1][1] - adapted_matrix[0][0] - adapted_matrix[2][2])
                w = (adapted_matrix[0][2] - adapted_matrix[2][0]) / s
                x = (adapted_matrix[0][1] + adapted_matrix[1][0]) / s
                y = 0.25 * s
                z = (adapted_matrix[1][2] + adapted_matrix[2][1]) / s
            else:
                s = 2.0 * math.sqrt(1.0 + adapted_matrix[2][2] - adapted_matrix[0][0] - adapted_matrix[1][1])
                w = (adapted_matrix[1][0] - adapted_matrix[0][1]) / s
                x = (adapted_matrix[0][2] + adapted_matrix[2][0]) / s
                y = (adapted_matrix[1][2] + adapted_matrix[2][1]) / s
                z = 0.25 * s
        
        # Create Unreal quaternion
        return unreal.Quat(x, y, z, w)
    except Exception as e:
        show_message(f"Error converting rotation matrix: {e}")
        return unreal.Quat(0, 0, 0, 1)  # Identity quaternion

def quat_to_rotator(quat):
    """Convert a quaternion to an Unreal rotator"""
    # Unreal has built-in conversion
    return quat.rotator()

def create_actor_for_entity_type(entity_type, location, rotation, editor_subsystem):
    """Create an appropriate actor based on entity type"""
    
    if entity_type == "Light":
        actor = editor_subsystem.spawn_actor_from_class(unreal.PointLight, location, rotation)
        # Configure light properties
        actor.light_component.intensity = 5000.0
        actor.light_component.set_light_color(unreal.LinearColor(1.0, 0.9, 0.8, 1.0))
        return actor
        
    elif entity_type == "MainCamera":
        actor = editor_subsystem.spawn_actor_from_class(unreal.CameraActor, location, rotation)
        return actor
        
    elif entity_type == "Telejump":
        actor = editor_subsystem.spawn_actor_from_class(unreal.TriggerBox, location, rotation)
        # Make it semi-transparent blue
        return actor
        
    elif entity_type == "PhysX":
        actor = editor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
        # Use a distinctive mesh for physics objects
        mesh = unreal.load_asset(TYPE_MESHES.get(entity_type, TYPE_MESHES["Default"]))
        if mesh:
            actor.static_mesh_component.set_static_mesh(mesh)
        return actor
        
    elif entity_type == "GlowMap":
        # Create a post-process volume or emissive marker
        actor = editor_subsystem.spawn_actor_from_class(unreal.PostProcessVolume, location, rotation)
        return actor
        
    elif entity_type == "SharedStream":
        # Create a visual indicator for streaming volumes
        actor = editor_subsystem.spawn_actor_from_class(unreal.TriggerVolume, location, rotation)
        return actor
        
    else:  # Default case for "Object" and others
        actor = editor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
        # Use a cube mesh by default
        mesh = unreal.load_asset(TYPE_MESHES.get(entity_type, TYPE_MESHES["Default"]))
        if mesh:
            actor.static_mesh_component.set_static_mesh(mesh)
        return actor

def apply_color_to_actor(actor, entity_type):
    """Apply color coding to an actor based on its type"""
    # Get the color for this entity type, or use default if not found
    color = TYPE_COLORS.get(entity_type, TYPE_COLORS["Default"])
    
    # Create a dynamic material instance and apply the color
    if hasattr(actor, 'static_mesh_component'):
        component = actor.static_mesh_component
        
        # Create a dynamic material instance
        material_instance = component.create_and_set_material_instance_dynamic(0)
        
        if material_instance:
            # Set the color
            material_instance.set_vector_parameter_value(
                'Color', 
                unreal.LinearColor(color[0], color[1], color[2], 1.0)
            )

def create_map_from_json(json_data, map_name, scale_factor):
    """
    Create a new map from JSON data
    
    Args:
        json_data: The loaded JSON data
        map_name: The name for the new map
        scale_factor: The scaling factor to apply to positions
    
    Returns:
        The path to the created level
    """
    show_message(f"Creating map '{map_name}' with scale factor {scale_factor}...")
    
    # Get the editor subsystem for level operations
    editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    
    # Create a new level
    new_level_path = f"/Game/Maps/{map_name}"
    editor_subsystem.new_level(new_level_path)
    
    # Track progress
    total_entities = len(json_data.get('entities', []))
    processed = 0
    
    # Create a folder structure for organization
    folder_structure = {}
    
    # Start time for performance tracking
    start_time = time.time()
    
    # Process each entity in the JSON
    for entity in json_data.get('entities', []):
        # Extract entity data
        entity_name = entity.get('name', 'Unknown')
        entity_type = entity.get('type', 'Object')
        
        # Find transform data and asset info in components
        transform_data = None
        asset_path = None
        is_hidden = False
        
        for component in entity.get('components', []):
            comp_class = component.get('class')
            
            if comp_class == 'NiTransformationComponent':
                transform_data = component
            elif comp_class == 'NiSceneGraphComponent':
                asset_path = component.get('unreal_path')
                # Check if the object is hidden
                if component.get('hidden', False):
                    is_hidden = True
        
        if transform_data:
            # Extract transform values
            translation = transform_data.get('translation', [0, 0, 0])
            rotation_matrix = transform_data.get('rotation')
            scale_value = transform_data.get('scale', 1.0)
            
            # Apply scaling factor to position
            scaled_translation = [t * scale_factor for t in translation]
            
            # Create location vector
            location = unreal.Vector(scaled_translation[0], scaled_translation[1], scaled_translation[2])
            
            # Convert rotation matrix to Unreal rotation
            rotation = unreal.Rotator(0, 0, 0)
            if rotation_matrix:
                quat = matrix_to_quaternion(rotation_matrix)
                rotation = quat_to_rotator(quat)
            
            # Create the appropriate actor based on entity type
            actor = create_actor_for_entity_type(entity_type, location, rotation, editor_subsystem)
            
            if actor:
                # Set the actor's name
                actor.set_actor_label(f"{entity_type}_{entity_name}")
                
                # Set the scale - apply the scale factor to maintain proportions
                scale_vector = unreal.Vector(scale_value, scale_value, scale_value)
                actor.set_actor_scale3d(scale_vector)
                
                # Set visibility based on hidden flag
                actor.set_actor_hidden_in_game(is_hidden)
                
                # Apply color coding based on entity type
                apply_color_to_actor(actor, entity_type)
                
                # Organize into folders
                folder_path = f"/{entity_type}"
                if entity_type not in folder_structure:
                    folder_structure[entity_type] = 0
                folder_structure[entity_type] += 1
                
                actor.set_folder_path(folder_path)
                
                # Store original asset path and other metadata as actor tags
                if asset_path:
                    actor.tags.append(f"OriginalAsset:{asset_path}")
        
        # Update progress
        processed += 1
        if processed % 50 == 0 or processed == total_entities:
            show_progress_bar(processed, total_entities, prefix='Building Map:', suffix='Complete')
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Print statistics
    show_message(f"\nMap creation complete in {elapsed_time:.2f} seconds!")
    show_message(f"Created {processed} objects:")
    
    for folder, count in folder_structure.items():
        show_message(f"  - {folder}: {count} objects")
    
    # Save the level
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    show_message(f"Level saved to {new_level_path}")
    
    return new_level_path

def main():
    """Main entry point for the script"""
    # Check if we have command line arguments
    command_args = unreal.PythonScriptLibrary.get_command_line_arguments()
    
    if len(command_args) >= 1:
        json_path = command_args[0]
    else:
        # No command line arguments, show a file dialog
        json_path = unreal.EditorDialog.open_file_dialog(
            "Select Dragonica JSON Map File",
            "",
            "JSON Files (*.json)|*.json"
        )
    
    if not json_path or not os.path.exists(json_path):
        show_message("Error: No valid JSON file selected")
        return
    
    # Extract map name from the JSON file name
    json_filename = os.path.basename(json_path)
    map_base_name = os.path.splitext(json_filename)[0]
    map_name = f"{MAP_NAME}_{map_base_name}"
    
    show_message(f"Loading JSON file: {json_path}")
    
    try:
        # Load the JSON data
        with open(json_path, 'r') as file:
            json_data = json.load(file)
        
        # Check if we should run the scale test
        run_scale_test = False
        if len(command_args) >= 2:
            run_scale_test = command_args[1].lower() == "test"
        
        if run_scale_test:
            # Create a scale test level
            test_scale_factors(json_data)
        else:
            # Create the actual map
            create_map_from_json(json_data, map_name, SCALE_FACTOR)
            
    except Exception as e:
        show_message(f"Error processing JSON file: {e}")
        import traceback
        show_message(traceback.format_exc())

if __name__ == "__main__":
    main()
