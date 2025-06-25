# nif_to_fbx.py
# Description: A Blender script to convert a .nif file to a .fbx file.
# Author: Gemini
#
# This script is intended to be run from the command line in Blender's background mode.
# It requires a NIF importer plugin to be installed and enabled in Blender.
#
# Command-Line Usage:
# blender --background --python nif_to_fbx.py -- <path_to_nif> <path_to_fbx>
#
# Example:
# blender --background --python nif_to_fbx.py -- "C:/path/to/model.nif" "C:/path/to/output.fbx"

import bpy
import sys
import os

def clear_scene():
    """Clears all objects from the current Blender scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def import_nif(nif_path):
    """Imports a .nif file into the current scene."""
    if not os.path.exists(nif_path):
        print(f"Error: NIF file not found at {nif_path}")
        return False
    
    try:
        # The exact operator name may depend on the specific NIF importer plugin being used.
        # 'import_scene.nif' is a common one.
        bpy.ops.import_scene.nif(filepath=nif_path)
        print(f"Successfully imported {nif_path}")
        return True
    except AttributeError:
        print("Error: NIF importer plugin not found or not enabled.")
        print("Please ensure you have a NIF importer installed in Blender.")
        return False
    except Exception as e:
        print(f"An error occurred during NIF import: {e}")
        return False

def export_fbx(fbx_path):
    """Exports the current scene to a .fbx file."""
    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(fbx_path), exist_ok=True)
        
        # FBX export settings can be fine-tuned here if needed.
        # These are generally safe defaults for game assets.
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=False,
            global_scale=1.0,
            apply_unit_scale=True,
            axis_forward='-Z',
            axis_up='Y',
            object_types={'MESH', 'ARMATURE', 'EMPTY'},
            use_mesh_modifiers=True,
            mesh_smooth_type='FACE',
            bake_anim=False # We handle animations separately if needed
        )
        print(f"Successfully exported {fbx_path}")
        return True
    except Exception as e:
        print(f"An error occurred during FBX export: {e}")
        return False

def main():
    """Main function to control the conversion process."""
    # Blender command-line arguments are passed after '--'
    try:
        argv = sys.argv[sys.argv.index("--") + 1:]
    except ValueError:
        argv = []

    if len(argv) != 2:
        print("Usage: blender --background --python nif_to_fbx.py -- <nif_path> <fbx_path>")
        sys.exit(1)

    nif_path = argv[0]
    fbx_path = argv[1]

    print("--- Starting NIF to FBX Conversion ---")
    print(f"Input NIF: {nif_path}")
    print(f"Output FBX: {fbx_path}")
    
    clear_scene()
    
    if import_nif(nif_path):
        export_fbx(fbx_path)
    
    print("--- Conversion Script Finished ---")

if __name__ == "__main__":
    main() 