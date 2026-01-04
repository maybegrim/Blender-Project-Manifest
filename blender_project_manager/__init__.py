"""
Blender Project Manager
Collect, consolidate and archive Blender projects with all external assets.
Inspired by Adobe Premiere Pro's Project Manager.
"""

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, IntProperty
from bpy.types import PropertyGroup, Operator, Panel, UIList
import os
import shutil
from pathlib import Path


# =============================================================================
# Property Groups
# =============================================================================

class PROJMAN_ExternalFile(PropertyGroup):
    """Represents an external file found in the project."""
    name: StringProperty(name="Name")
    filepath: StringProperty(name="File Path")
    file_type: StringProperty(name="Type")  # image, sound, font, library, etc.
    file_size: IntProperty(name="Size (bytes)")
    exists: BoolProperty(name="Exists", default=True)
    selected: BoolProperty(name="Selected", default=True)


class PROJMAN_Properties(PropertyGroup):
    """Main addon properties."""

    destination_path: StringProperty(
        name="Destination",
        description="Folder where the project will be collected",
        subtype='DIR_PATH',
        default=""
    )

    include_images: BoolProperty(
        name="Images",
        description="Include image textures",
        default=True
    )

    include_sounds: BoolProperty(
        name="Sounds",
        description="Include audio files",
        default=True
    )

    include_fonts: BoolProperty(
        name="Fonts",
        description="Include font files",
        default=True
    )

    include_videos: BoolProperty(
        name="Video Clips",
        description="Include movie clips used for tracking or compositing",
        default=True
    )

    include_caches: BoolProperty(
        name="Cache Files",
        description="Include Alembic, USD and other cache files",
        default=True
    )

    include_volumes: BoolProperty(
        name="Volumes",
        description="Include OpenVDB volume files",
        default=True
    )

    include_libraries: BoolProperty(
        name="Linked Libraries",
        description="Include linked .blend files",
        default=True
    )

    exclude_unused: BoolProperty(
        name="Exclude Unused Data",
        description="Skip files that are loaded but not used in the scene",
        default=False
    )

    flatten_folders: BoolProperty(
        name="Flatten Folder Structure",
        description="Put all files in a single folder instead of preserving structure",
        default=False
    )

    rename_to_match: BoolProperty(
        name="Rename to Match Datablock",
        description="Rename copied files to match their Blender datablock names",
        default=False
    )

    copy_blend_file: BoolProperty(
        name="Copy .blend File",
        description="Copy the current .blend file to the destination",
        default=True
    )

    relink_paths: BoolProperty(
        name="Relink Paths in Copy",
        description="Update file paths in the copied .blend to point to the new locations",
        default=True
    )

    # Scan results
    external_files: CollectionProperty(type=PROJMAN_ExternalFile)
    active_file_index: IntProperty(name="Active File Index", default=0)

    # Statistics
    total_files: IntProperty(name="Total Files", default=0)
    total_size: IntProperty(name="Total Size", default=0)
    missing_files: IntProperty(name="Missing Files", default=0)


# =============================================================================
# Utility Functions
# =============================================================================

def get_absolute_path(filepath):
    """Convert a Blender path to an absolute path."""
    if filepath.startswith("//"):
        # Relative path
        blend_dir = os.path.dirname(bpy.data.filepath)
        return os.path.normpath(os.path.join(blend_dir, filepath[2:]))
    return os.path.normpath(filepath)


def get_file_size(filepath):
    """Get file size in bytes, returns 0 if file doesn't exist."""
    try:
        return os.path.getsize(filepath)
    except (OSError, FileNotFoundError):
        return 0


def format_size(size_bytes):
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def is_datablock_used(datablock):
    """Check if a datablock is actually used in the project."""
    return datablock.users > 0


def scan_external_files(context):
    """Scan the project for all external file references."""
    props = context.scene.project_manager
    props.external_files.clear()

    total_size = 0
    missing_count = 0

    # Check if blend file is saved
    if not bpy.data.filepath:
        return {"error": "Please save the .blend file first"}

    # Scan Images
    if props.include_images:
        for img in bpy.data.images:
            # Skip packed, generated, or viewer images
            if img.packed_file or img.source in {'GENERATED', 'VIEWER'}:
                continue
            if props.exclude_unused and not is_datablock_used(img):
                continue
            if img.filepath:
                abs_path = get_absolute_path(img.filepath)
                exists = os.path.isfile(abs_path)
                size = get_file_size(abs_path) if exists else 0

                file_entry = props.external_files.add()
                file_entry.name = img.name
                file_entry.filepath = abs_path
                file_entry.file_type = "Image"
                file_entry.file_size = size
                file_entry.exists = exists
                file_entry.selected = True

                total_size += size
                if not exists:
                    missing_count += 1

    # Scan Sounds
    if props.include_sounds:
        for sound in bpy.data.sounds:
            if sound.packed_file:
                continue
            if props.exclude_unused and not is_datablock_used(sound):
                continue
            if sound.filepath:
                abs_path = get_absolute_path(sound.filepath)
                exists = os.path.isfile(abs_path)
                size = get_file_size(abs_path) if exists else 0

                file_entry = props.external_files.add()
                file_entry.name = sound.name
                file_entry.filepath = abs_path
                file_entry.file_type = "Sound"
                file_entry.file_size = size
                file_entry.exists = exists
                file_entry.selected = True

                total_size += size
                if not exists:
                    missing_count += 1

    # Scan Fonts
    if props.include_fonts:
        for font in bpy.data.fonts:
            if font.packed_file:
                continue
            # Built-in font has no filepath
            if not font.filepath or font.filepath == "<builtin>":
                continue
            if props.exclude_unused and not is_datablock_used(font):
                continue

            abs_path = get_absolute_path(font.filepath)
            exists = os.path.isfile(abs_path)
            size = get_file_size(abs_path) if exists else 0

            file_entry = props.external_files.add()
            file_entry.name = font.name
            file_entry.filepath = abs_path
            file_entry.file_type = "Font"
            file_entry.file_size = size
            file_entry.exists = exists
            file_entry.selected = True

            total_size += size
            if not exists:
                missing_count += 1

    # Scan Movie Clips
    if props.include_videos:
        for clip in bpy.data.movieclips:
            if clip.filepath:
                abs_path = get_absolute_path(clip.filepath)
                exists = os.path.isfile(abs_path)
                size = get_file_size(abs_path) if exists else 0

                file_entry = props.external_files.add()
                file_entry.name = clip.name
                file_entry.filepath = abs_path
                file_entry.file_type = "Movie Clip"
                file_entry.file_size = size
                file_entry.exists = exists
                file_entry.selected = True

                total_size += size
                if not exists:
                    missing_count += 1

    # Scan Cache Files (Alembic, USD, etc.)
    if props.include_caches:
        for cache in bpy.data.cache_files:
            if cache.filepath:
                abs_path = get_absolute_path(cache.filepath)
                exists = os.path.isfile(abs_path)
                size = get_file_size(abs_path) if exists else 0

                file_entry = props.external_files.add()
                file_entry.name = cache.name
                file_entry.filepath = abs_path
                file_entry.file_type = "Cache File"
                file_entry.file_size = size
                file_entry.exists = exists
                file_entry.selected = True

                total_size += size
                if not exists:
                    missing_count += 1

    # Scan Volumes (VDB)
    if props.include_volumes:
        for volume in bpy.data.volumes:
            if volume.filepath:
                abs_path = get_absolute_path(volume.filepath)
                exists = os.path.isfile(abs_path)
                size = get_file_size(abs_path) if exists else 0

                file_entry = props.external_files.add()
                file_entry.name = volume.name
                file_entry.filepath = abs_path
                file_entry.file_type = "Volume"
                file_entry.file_size = size
                file_entry.exists = exists
                file_entry.selected = True

                total_size += size
                if not exists:
                    missing_count += 1

    # Scan Linked Libraries
    if props.include_libraries:
        for lib in bpy.data.libraries:
            if lib.filepath:
                abs_path = get_absolute_path(lib.filepath)
                exists = os.path.isfile(abs_path)
                size = get_file_size(abs_path) if exists else 0

                file_entry = props.external_files.add()
                file_entry.name = lib.name
                file_entry.filepath = abs_path
                file_entry.file_type = "Library"
                file_entry.file_size = size
                file_entry.exists = exists
                file_entry.selected = True

                total_size += size
                if not exists:
                    missing_count += 1

    props.total_files = len(props.external_files)
    props.total_size = total_size
    props.missing_files = missing_count

    return {"success": True, "count": props.total_files}


# =============================================================================
# Operators
# =============================================================================

class PROJMAN_OT_scan_files(Operator):
    """Scan the project for external file references"""
    bl_idname = "project_manager.scan_files"
    bl_label = "Scan Project"
    bl_options = {'REGISTER'}

    def execute(self, context):
        result = scan_external_files(context)

        if "error" in result:
            self.report({'ERROR'}, result["error"])
            return {'CANCELLED'}

        props = context.scene.project_manager
        self.report({'INFO'}, f"Found {props.total_files} external files ({format_size(props.total_size)})")
        return {'FINISHED'}


class PROJMAN_OT_collect_files(Operator):
    """Collect all project files to the destination folder"""
    bl_idname = "project_manager.collect_files"
    bl_label = "Collect Project"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.project_manager

        # Validation
        if not props.destination_path:
            self.report({'ERROR'}, "Please select a destination folder")
            return {'CANCELLED'}

        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save the .blend file first")
            return {'CANCELLED'}

        if len(props.external_files) == 0:
            self.report({'WARNING'}, "No files to collect. Run 'Scan Project' first.")
            return {'CANCELLED'}

        dest_path = bpy.path.abspath(props.destination_path)

        # Create destination folder if it doesn't exist
        os.makedirs(dest_path, exist_ok=True)

        # Create subfolders for organization
        if not props.flatten_folders:
            for folder in ["textures", "sounds", "fonts", "videos", "caches", "volumes", "libraries"]:
                os.makedirs(os.path.join(dest_path, folder), exist_ok=True)

        # Track path mappings for relinking
        path_mapping = {}
        copied_count = 0
        failed_count = 0

        # Copy files
        for file_entry in props.external_files:
            if not file_entry.selected:
                continue

            if not file_entry.exists:
                failed_count += 1
                continue

            try:
                # Determine destination subfolder
                if props.flatten_folders:
                    dest_subfolder = ""
                else:
                    type_to_folder = {
                        "Image": "textures",
                        "Sound": "sounds",
                        "Font": "fonts",
                        "Movie Clip": "videos",
                        "Cache File": "caches",
                        "Volume": "volumes",
                        "Library": "libraries"
                    }
                    dest_subfolder = type_to_folder.get(file_entry.file_type, "")

                # Determine filename
                if props.rename_to_match:
                    # Use datablock name + original extension
                    _, ext = os.path.splitext(file_entry.filepath)
                    new_filename = file_entry.name + ext
                else:
                    new_filename = os.path.basename(file_entry.filepath)

                # Build full destination path
                if dest_subfolder:
                    dest_file = os.path.join(dest_path, dest_subfolder, new_filename)
                else:
                    dest_file = os.path.join(dest_path, new_filename)

                # Handle duplicates
                base, ext = os.path.splitext(dest_file)
                counter = 1
                while os.path.exists(dest_file):
                    dest_file = f"{base}_{counter}{ext}"
                    counter += 1

                # Copy the file
                shutil.copy2(file_entry.filepath, dest_file)
                path_mapping[file_entry.filepath] = dest_file
                copied_count += 1

            except Exception as e:
                self.report({'WARNING'}, f"Failed to copy {file_entry.name}: {str(e)}")
                failed_count += 1

        # Copy and relink .blend file
        if props.copy_blend_file:
            blend_name = os.path.basename(bpy.data.filepath)
            dest_blend = os.path.join(dest_path, blend_name)

            # Handle duplicate blend file name
            base, ext = os.path.splitext(dest_blend)
            counter = 1
            while os.path.exists(dest_blend):
                dest_blend = f"{base}_{counter}{ext}"
                counter += 1

            if props.relink_paths:
                # Save current file first to preserve state
                bpy.ops.wm.save_mainfile()

                # Remap paths to relative paths pointing to new locations
                for file_entry in props.external_files:
                    if file_entry.filepath in path_mapping:
                        new_path = path_mapping[file_entry.filepath]
                        # Make path relative to destination blend file
                        rel_path = os.path.relpath(new_path, dest_path)
                        rel_path = "//" + rel_path.replace("\\", "/")

                        # Update the actual datablock path
                        self._update_datablock_path(file_entry.name, file_entry.file_type, rel_path)

                # Save to destination
                bpy.ops.wm.save_as_mainfile(filepath=dest_blend, copy=True)

                # Restore original paths
                bpy.ops.wm.revert_mainfile()
            else:
                # Just copy the blend file without relinking
                shutil.copy2(bpy.data.filepath, dest_blend)

        self.report({'INFO'}, f"Collected {copied_count} files to {dest_path}" +
                    (f" ({failed_count} failed)" if failed_count > 0 else ""))
        return {'FINISHED'}

    def _update_datablock_path(self, name, file_type, new_path):
        """Update the filepath of a datablock."""
        try:
            if file_type == "Image":
                if name in bpy.data.images:
                    bpy.data.images[name].filepath = new_path
            elif file_type == "Sound":
                if name in bpy.data.sounds:
                    bpy.data.sounds[name].filepath = new_path
            elif file_type == "Font":
                if name in bpy.data.fonts:
                    bpy.data.fonts[name].filepath = new_path
            elif file_type == "Movie Clip":
                if name in bpy.data.movieclips:
                    bpy.data.movieclips[name].filepath = new_path
            elif file_type == "Cache File":
                if name in bpy.data.cache_files:
                    bpy.data.cache_files[name].filepath = new_path
            elif file_type == "Volume":
                if name in bpy.data.volumes:
                    bpy.data.volumes[name].filepath = new_path
            elif file_type == "Library":
                if name in bpy.data.libraries:
                    bpy.data.libraries[name].filepath = new_path
        except Exception:
            pass  # Silently fail for individual path updates


class PROJMAN_OT_select_all(Operator):
    """Select all files in the list"""
    bl_idname = "project_manager.select_all"
    bl_label = "Select All"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.project_manager
        for file_entry in props.external_files:
            file_entry.selected = True
        return {'FINISHED'}


class PROJMAN_OT_deselect_all(Operator):
    """Deselect all files in the list"""
    bl_idname = "project_manager.deselect_all"
    bl_label = "Deselect All"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.project_manager
        for file_entry in props.external_files:
            file_entry.selected = False
        return {'FINISHED'}


class PROJMAN_OT_open_destination(Operator):
    """Open the destination folder in the file browser"""
    bl_idname = "project_manager.open_destination"
    bl_label = "Open Destination"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.project_manager

        if not props.destination_path:
            self.report({'ERROR'}, "No destination folder set")
            return {'CANCELLED'}

        dest_path = bpy.path.abspath(props.destination_path)

        if not os.path.isdir(dest_path):
            self.report({'ERROR'}, "Destination folder does not exist")
            return {'CANCELLED'}

        # Open folder in system file browser
        import subprocess
        import platform

        system = platform.system()
        if system == "Windows":
            os.startfile(dest_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", dest_path])
        else:  # Linux
            subprocess.run(["xdg-open", dest_path])

        return {'FINISHED'}


# =============================================================================
# UI List
# =============================================================================

class PROJMAN_UL_files(UIList):
    """UI List for displaying external files."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            # Selection checkbox
            row.prop(item, "selected", text="")

            # Status icon
            if not item.exists:
                row.label(text="", icon='ERROR')
            else:
                type_icons = {
                    "Image": 'IMAGE_DATA',
                    "Sound": 'SOUND',
                    "Font": 'FONT_DATA',
                    "Movie Clip": 'FILE_MOVIE',
                    "Cache File": 'FILE_CACHE',
                    "Volume": 'VOLUME_DATA',
                    "Library": 'LIBRARY_DATA_DIRECT'
                }
                row.label(text="", icon=type_icons.get(item.file_type, 'FILE'))

            # File name
            row.label(text=item.name)

            # File size
            if item.exists:
                row.label(text=format_size(item.file_size))
            else:
                row.label(text="MISSING", icon='ERROR')

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE')


# =============================================================================
# Panels
# =============================================================================

class PROJMAN_PT_main(Panel):
    """Main panel for Project Manager."""
    bl_label = "Project Manager"
    bl_idname = "PROJMAN_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        # Destination folder
        layout.label(text="Destination Folder:")
        row = layout.row(align=True)
        row.prop(props, "destination_path", text="")
        row.operator("project_manager.open_destination", text="", icon='FILE_FOLDER')


class PROJMAN_PT_options(Panel):
    """Options panel for Project Manager."""
    bl_label = "Include"
    bl_idname = "PROJMAN_PT_options"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        # File type toggles
        col = layout.column(align=True)

        row = col.row(align=True)
        row.prop(props, "include_images", toggle=True)
        row.prop(props, "include_sounds", toggle=True)
        row.prop(props, "include_fonts", toggle=True)

        row = col.row(align=True)
        row.prop(props, "include_videos", toggle=True)
        row.prop(props, "include_caches", toggle=True)
        row.prop(props, "include_volumes", toggle=True)

        row = col.row(align=True)
        row.prop(props, "include_libraries", toggle=True)


class PROJMAN_PT_settings(Panel):
    """Settings panel for Project Manager."""
    bl_label = "Settings"
    bl_idname = "PROJMAN_PT_settings"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        col = layout.column(align=True)
        col.prop(props, "exclude_unused")
        col.prop(props, "flatten_folders")
        col.prop(props, "rename_to_match")

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "copy_blend_file")

        sub = col.column(align=True)
        sub.enabled = props.copy_blend_file
        sub.prop(props, "relink_paths")


class PROJMAN_PT_files(Panel):
    """Files panel for Project Manager."""
    bl_label = "External Files"
    bl_idname = "PROJMAN_PT_files"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        # Scan button
        layout.operator("project_manager.scan_files", icon='FILE_REFRESH')

        # Statistics
        if props.total_files > 0:
            box = layout.box()
            col = box.column(align=True)
            col.label(text=f"Total Files: {props.total_files}")
            col.label(text=f"Total Size: {format_size(props.total_size)}")
            if props.missing_files > 0:
                col.label(text=f"Missing: {props.missing_files}", icon='ERROR')

        # File list
        if len(props.external_files) > 0:
            row = layout.row()
            row.template_list(
                "PROJMAN_UL_files", "",
                props, "external_files",
                props, "active_file_index",
                rows=5
            )

            # Selection buttons
            row = layout.row(align=True)
            row.operator("project_manager.select_all", text="All")
            row.operator("project_manager.deselect_all", text="None")

            # Show selected file path
            if props.active_file_index < len(props.external_files):
                active = props.external_files[props.active_file_index]
                layout.label(text=active.filepath, icon='FILE')


class PROJMAN_PT_actions(Panel):
    """Actions panel for Project Manager."""
    bl_label = "Collect"
    bl_idname = "PROJMAN_PT_actions"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        # Count selected files
        selected_count = sum(1 for f in props.external_files if f.selected)
        selected_size = sum(f.file_size for f in props.external_files if f.selected and f.exists)

        if selected_count > 0:
            layout.label(text=f"Selected: {selected_count} files ({format_size(selected_size)})")

        # Collect button
        row = layout.row()
        row.scale_y = 1.5
        row.operator("project_manager.collect_files", icon='EXPORT')


# =============================================================================
# Registration
# =============================================================================

classes = (
    PROJMAN_ExternalFile,
    PROJMAN_Properties,
    PROJMAN_OT_scan_files,
    PROJMAN_OT_collect_files,
    PROJMAN_OT_select_all,
    PROJMAN_OT_deselect_all,
    PROJMAN_OT_open_destination,
    PROJMAN_UL_files,
    PROJMAN_PT_main,
    PROJMAN_PT_options,
    PROJMAN_PT_files,
    PROJMAN_PT_settings,
    PROJMAN_PT_actions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.project_manager = bpy.props.PointerProperty(type=PROJMAN_Properties)


def unregister():
    del bpy.types.Scene.project_manager

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
