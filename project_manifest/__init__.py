import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty, FloatProperty
from bpy.types import PropertyGroup, Operator, Panel, UIList
import glob
import hashlib
import os
import re
import shutil


class PROJMAN_ExternalFile(PropertyGroup):
    name: StringProperty(name="Name")
    filepath: StringProperty(name="File Path")
    file_type: StringProperty(name="Type")
    file_size: FloatProperty(name="Size (bytes)")
    exists: BoolProperty(name="Exists", default=True)
    selected: BoolProperty(name="Selected", default=True)
    file_hash: StringProperty(name="File Hash")
    member_files: StringProperty(name="Member Files")


class PROJMAN_DuplicateGroup(PropertyGroup):
    hash_value: StringProperty(name="Hash")
    file_count: IntProperty(name="Count")
    file_names: StringProperty(name="Files")
    file_type: StringProperty(name="Type")
    total_size: FloatProperty(name="Total Size")


class PROJMAN_Properties(PropertyGroup):

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

    include_sequencer: BoolProperty(
        name="Sequencer Strips",
        description="Include movie and image strips from the Video Sequencer",
        default=True
    )

    pack_images: BoolProperty(
        name="Images",
        description="Pack image textures into the .blend file",
        default=True
    )

    pack_sounds: BoolProperty(
        name="Sounds",
        description="Pack audio files into the .blend file",
        default=True
    )

    pack_fonts: BoolProperty(
        name="Fonts",
        description="Pack font files into the .blend file",
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

    external_files: CollectionProperty(type=PROJMAN_ExternalFile)
    active_file_index: IntProperty(name="Active File Index", default=0)

    total_files: IntProperty(name="Total Files", default=0)
    total_size: FloatProperty(name="Total Size", default=0.0)
    missing_files: IntProperty(name="Missing Files", default=0)

    duplicate_groups: CollectionProperty(type=PROJMAN_DuplicateGroup)
    active_duplicate_index: IntProperty(name="Active Duplicate Index", default=0)
    duplicate_count: IntProperty(name="Duplicate Count", default=0)
    duplicate_wasted_size: FloatProperty(name="Wasted Size", default=0.0)


TYPE_TO_FOLDER = {
    "Image": "textures",
    "Sound": "sounds",
    "Font": "fonts",
    "Movie Clip": "videos",
    "Cache File": "caches",
    "Volume": "volumes",
    "Library": "libraries",
    "Movie Strip": "videos",
    "Image Strip": "textures",
}

TYPE_ICONS = {
    "Image": 'IMAGE_DATA',
    "Sound": 'SOUND',
    "Font": 'FONT_DATA',
    "Movie Clip": 'FILE_MOVIE',
    "Cache File": 'FILE_CACHE',
    "Volume": 'VOLUME_DATA',
    "Library": 'LIBRARY_DATA_DIRECT',
    "Movie Strip": 'SEQUENCE',
    "Image Strip": 'RENDERLAYERS',
}


def get_file_size(filepath):
    try:
        return os.path.getsize(filepath)
    except (OSError, FileNotFoundError):
        return 0


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def compute_file_hash(filepath, chunk_size=65536):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, FileNotFoundError):
        return None


def resolve_path(filepath, datablock=None):
    library = getattr(datablock, "library", None) if datablock is not None else None
    return os.path.normpath(bpy.path.abspath(filepath, library=library))


def expand_frame_sequence(filepath):
    directory, basename = os.path.split(filepath)
    match = re.search(r"(\d+)(\.[^.]+)?$", basename)
    if not match:
        return [filepath]
    prefix = basename[:match.start(1)]
    suffix = basename[match.end(1):]
    pattern = os.path.join(
        glob.escape(directory),
        glob.escape(prefix) + "[0-9]" * len(match.group(1)) + glob.escape(suffix)
    )
    files = sorted(glob.glob(pattern))
    return files if files else [filepath]


def expand_udim_tiles(filepath, image):
    members = []
    for tile in image.tiles:
        number = tile.number
        u = (number - 1001) % 10 + 1
        v = (number - 1001) // 10 + 1
        path = filepath.replace("<UDIM>", str(number)).replace("<UVTILE>", f"u{u}_v{v}")
        members.append(path)
    return members if members else [filepath]


def entry_member_files(entry):
    if entry.member_files:
        return entry.member_files.split("\n")
    return [entry.filepath]


def iter_strips(scene):
    editor = scene.sequence_editor
    if editor is None:
        return ()
    if hasattr(editor, "strips_all"):
        return editor.strips_all
    return editor.sequences_all


def find_strip(name):
    for scene in bpy.data.scenes:
        for strip in iter_strips(scene):
            if strip.name == name:
                return strip
    return None


def get_data_collection(file_type):
    return {
        "Image": bpy.data.images,
        "Sound": bpy.data.sounds,
        "Font": bpy.data.fonts,
        "Movie Clip": bpy.data.movieclips,
        "Cache File": bpy.data.cache_files,
        "Volume": bpy.data.volumes,
        "Library": bpy.data.libraries,
    }.get(file_type)


def apply_new_path(name, file_type, new_path):
    if file_type == "Movie Strip":
        strip = find_strip(name)
        if strip is None:
            return None
        old = strip.filepath
        strip.filepath = new_path
        return (strip, "filepath", old)
    if file_type == "Image Strip":
        strip = find_strip(name)
        if strip is None:
            return None
        old = strip.directory
        new_dir = os.path.dirname(new_path)
        strip.directory = new_dir if new_dir.endswith("/") else new_dir + "/"
        return (strip, "directory", old)
    collection = get_data_collection(file_type)
    if collection is None:
        return None
    datablock = collection.get((name, None))
    if datablock is None:
        return None
    old = datablock.filepath
    datablock.filepath = new_path
    return (datablock, "filepath", old)


def scan_external_files(context):
    props = context.scene.project_manager
    props.external_files.clear()

    if not bpy.data.filepath:
        return {"error": "Please save the .blend file first"}

    total_size = 0.0
    missing_count = 0
    seen_paths = set()

    def add_entry(name, filepath, file_type, members=None):
        nonlocal total_size, missing_count
        file_list = members if members else [filepath]
        existing = [f for f in file_list if os.path.isfile(f)]
        exists = len(existing) > 0
        size = float(sum(get_file_size(f) for f in existing))

        entry = props.external_files.add()
        entry.name = name
        entry.filepath = filepath
        entry.file_type = file_type
        entry.file_size = size
        entry.exists = exists
        entry.selected = True
        entry.member_files = "\n".join(file_list) if members else ""

        if filepath not in seen_paths:
            seen_paths.add(filepath)
            total_size += size
            if not exists:
                missing_count += 1

    if props.include_images:
        for img in bpy.data.images:
            if img.packed_file or img.source in {'GENERATED', 'VIEWER'}:
                continue
            if props.exclude_unused and img.users == 0:
                continue
            if not img.filepath:
                continue
            abs_path = resolve_path(img.filepath, img)
            if img.source == 'TILED':
                add_entry(img.name, abs_path, "Image", expand_udim_tiles(abs_path, img))
            elif img.source == 'SEQUENCE':
                add_entry(img.name, abs_path, "Image", expand_frame_sequence(abs_path))
            else:
                add_entry(img.name, abs_path, "Image")

    if props.include_sounds:
        for sound in bpy.data.sounds:
            if sound.packed_file:
                continue
            if props.exclude_unused and sound.users == 0:
                continue
            if sound.filepath:
                add_entry(sound.name, resolve_path(sound.filepath, sound), "Sound")

    if props.include_fonts:
        for font in bpy.data.fonts:
            if font.packed_file:
                continue
            if not font.filepath or font.filepath == "<builtin>":
                continue
            if props.exclude_unused and font.users == 0:
                continue
            add_entry(font.name, resolve_path(font.filepath, font), "Font")

    if props.include_videos:
        for clip in bpy.data.movieclips:
            if props.exclude_unused and clip.users == 0:
                continue
            if not clip.filepath:
                continue
            abs_path = resolve_path(clip.filepath, clip)
            if clip.source == 'SEQUENCE':
                add_entry(clip.name, abs_path, "Movie Clip", expand_frame_sequence(abs_path))
            else:
                add_entry(clip.name, abs_path, "Movie Clip")

    if props.include_caches:
        for cache in bpy.data.cache_files:
            if props.exclude_unused and cache.users == 0:
                continue
            if cache.filepath:
                add_entry(cache.name, resolve_path(cache.filepath, cache), "Cache File")

    if props.include_volumes:
        for volume in bpy.data.volumes:
            if props.exclude_unused and volume.users == 0:
                continue
            if not volume.filepath:
                continue
            abs_path = resolve_path(volume.filepath, volume)
            if volume.is_sequence:
                add_entry(volume.name, abs_path, "Volume", expand_frame_sequence(abs_path))
            else:
                add_entry(volume.name, abs_path, "Volume")

    if props.include_libraries:
        for lib in bpy.data.libraries:
            if props.exclude_unused and len(lib.users_id) == 0:
                continue
            if lib.filepath:
                add_entry(lib.name, resolve_path(lib.filepath, lib), "Library")

    if props.include_sequencer:
        for scene in bpy.data.scenes:
            for strip in iter_strips(scene):
                if strip.type == 'MOVIE':
                    if strip.filepath:
                        add_entry(strip.name, resolve_path(strip.filepath), "Movie Strip")
                elif strip.type == 'IMAGE':
                    if strip.directory and len(strip.elements) > 0:
                        directory = resolve_path(strip.directory)
                        members = [os.path.join(directory, e.filename) for e in strip.elements]
                        add_entry(strip.name, members[0], "Image Strip", members)

    props.total_files = len(props.external_files)
    props.total_size = total_size
    props.missing_files = missing_count

    return {"success": True, "count": props.total_files}


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
        os.makedirs(dest_path, exist_ok=True)

        if not props.flatten_folders:
            for folder in sorted(set(TYPE_TO_FOLDER.values())):
                os.makedirs(os.path.join(dest_path, folder), exist_ok=True)

        path_mapping = {}
        copied_count = 0
        failed_count = 0

        for file_entry in props.external_files:
            if not file_entry.selected:
                continue

            if file_entry.filepath in path_mapping:
                continue

            if not file_entry.exists:
                failed_count += 1
                continue

            try:
                if props.flatten_folders:
                    target_dir = dest_path
                else:
                    subfolder = TYPE_TO_FOLDER.get(file_entry.file_type, "")
                    target_dir = os.path.join(dest_path, subfolder) if subfolder else dest_path

                if file_entry.member_files:
                    members = [f for f in entry_member_files(file_entry) if os.path.isfile(f)]
                    targets = [os.path.join(target_dir, os.path.basename(f)) for f in members]
                    if any(os.path.exists(t) for t in targets):
                        safe_name = re.sub(r"[\\/:]", "_", file_entry.name)
                        counter = 1
                        while os.path.exists(os.path.join(target_dir, f"{safe_name}_{counter}")):
                            counter += 1
                        target_dir = os.path.join(target_dir, f"{safe_name}_{counter}")
                        os.makedirs(target_dir, exist_ok=True)
                    for f in members:
                        shutil.copy2(f, os.path.join(target_dir, os.path.basename(f)))
                    path_mapping[file_entry.filepath] = os.path.join(
                        target_dir, os.path.basename(file_entry.filepath))
                    copied_count += 1
                else:
                    if props.rename_to_match:
                        _, ext = os.path.splitext(file_entry.filepath)
                        new_filename = re.sub(r"[\\/:]", "_", file_entry.name) + ext
                    else:
                        new_filename = os.path.basename(file_entry.filepath)

                    dest_file = os.path.join(target_dir, new_filename)
                    base, ext = os.path.splitext(dest_file)
                    counter = 1
                    while os.path.exists(dest_file):
                        dest_file = f"{base}_{counter}{ext}"
                        counter += 1

                    shutil.copy2(file_entry.filepath, dest_file)
                    path_mapping[file_entry.filepath] = dest_file
                    copied_count += 1

            except Exception as e:
                self.report({'WARNING'}, f"Failed to copy {file_entry.name}: {str(e)}")
                failed_count += 1

        if props.copy_blend_file:
            blend_name = os.path.basename(bpy.data.filepath)
            dest_blend = os.path.join(dest_path, blend_name)

            base, ext = os.path.splitext(dest_blend)
            counter = 1
            while os.path.exists(dest_blend):
                dest_blend = f"{base}_{counter}{ext}"
                counter += 1

            if props.relink_paths:
                restores = []
                try:
                    for file_entry in props.external_files:
                        new_abs = path_mapping.get(file_entry.filepath)
                        if not new_abs:
                            continue
                        rel_path = "//" + os.path.relpath(new_abs, dest_path).replace("\\", "/")
                        restore = apply_new_path(file_entry.name, file_entry.file_type, rel_path)
                        if restore is not None:
                            restores.append(restore)
                    bpy.ops.wm.save_as_mainfile(filepath=dest_blend, copy=True, relative_remap=False)
                finally:
                    for owner, attr, old in reversed(restores):
                        setattr(owner, attr, old)
            else:
                shutil.copy2(bpy.data.filepath, dest_blend)

        self.report({'INFO'}, f"Collected {copied_count} files to {dest_path}" +
                    (f" ({failed_count} failed)" if failed_count > 0 else ""))
        return {'FINISHED'}


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

        import subprocess
        import platform

        system = platform.system()
        if system == "Windows":
            os.startfile(dest_path)
        elif system == "Darwin":
            subprocess.run(["open", dest_path])
        else:
            subprocess.run(["xdg-open", dest_path])

        return {'FINISHED'}


class PROJMAN_OT_pack_all(Operator):
    """Pack all external files into the .blend file"""
    bl_idname = "project_manager.pack_all"
    bl_label = "Pack All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.project_manager
        packed_count = 0
        failed_count = 0

        if props.pack_images:
            for img in bpy.data.images:
                if img.packed_file or img.source in {'GENERATED', 'VIEWER'}:
                    continue
                if props.exclude_unused and img.users == 0:
                    continue
                if img.filepath:
                    try:
                        img.pack()
                        packed_count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"Failed to pack {img.name}: {str(e)}")
                        failed_count += 1

        if props.pack_sounds:
            for sound in bpy.data.sounds:
                if sound.packed_file:
                    continue
                if props.exclude_unused and sound.users == 0:
                    continue
                if sound.filepath:
                    try:
                        sound.pack()
                        packed_count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"Failed to pack {sound.name}: {str(e)}")
                        failed_count += 1

        if props.pack_fonts:
            for font in bpy.data.fonts:
                if font.packed_file:
                    continue
                if not font.filepath or font.filepath == "<builtin>":
                    continue
                if props.exclude_unused and font.users == 0:
                    continue
                try:
                    font.pack()
                    packed_count += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to pack {font.name}: {str(e)}")
                    failed_count += 1

        msg = f"Packed {packed_count} files"
        if failed_count > 0:
            msg += f" ({failed_count} failed)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class PROJMAN_OT_unpack_all(Operator):
    """Unpack all packed files to the current directory"""
    bl_idname = "project_manager.unpack_all"
    bl_label = "Unpack All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save the .blend file first")
            return {'CANCELLED'}

        try:
            bpy.ops.file.unpack_all(method='USE_LOCAL')
            self.report({'INFO'}, "Unpacked all files")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to unpack: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class PROJMAN_OT_scan_duplicates(Operator):
    """Scan for duplicate files in the project"""
    bl_idname = "project_manager.scan_duplicates"
    bl_label = "Find Duplicates"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.project_manager
        props.duplicate_groups.clear()

        if len(props.external_files) == 0:
            scan_external_files(context)

        hash_map = {}

        for file_entry in props.external_files:
            if not file_entry.exists:
                continue

            file_hash = compute_file_hash(file_entry.filepath)
            if file_hash:
                file_entry.file_hash = file_hash
                if file_hash not in hash_map:
                    hash_map[file_hash] = []
                hash_map[file_hash].append({
                    'name': file_entry.name,
                    'filepath': file_entry.filepath,
                    'file_type': file_entry.file_type,
                    'size': file_entry.file_size
                })

        duplicate_count = 0
        wasted_size = 0.0

        for file_hash, files in hash_map.items():
            unique_paths = {f['filepath'] for f in files}
            if len(unique_paths) > 1:
                dup_group = props.duplicate_groups.add()
                dup_group.hash_value = file_hash
                dup_group.file_count = len(files)
                dup_group.file_names = ", ".join([f['name'] for f in files])
                dup_group.file_type = files[0]['file_type']
                dup_group.total_size = files[0]['size'] * len(unique_paths)

                duplicate_count += len(unique_paths) - 1
                wasted_size += files[0]['size'] * (len(unique_paths) - 1)

        props.duplicate_count = duplicate_count
        props.duplicate_wasted_size = wasted_size

        if duplicate_count > 0:
            self.report({'INFO'}, f"Found {duplicate_count} duplicate files ({format_size(wasted_size)} wasted)")
        else:
            self.report({'INFO'}, "No duplicate files found")

        return {'FINISHED'}


class PROJMAN_OT_consolidate_duplicates(Operator):
    """Make all duplicate files point to a single source"""
    bl_idname = "project_manager.consolidate_duplicates"
    bl_label = "Consolidate Duplicates"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.project_manager

        if len(props.duplicate_groups) == 0:
            self.report({'WARNING'}, "No duplicates found. Run 'Find Duplicates' first.")
            return {'CANCELLED'}

        consolidated_count = 0

        hash_to_files = {}
        for file_entry in props.external_files:
            if file_entry.file_hash and file_entry.exists:
                if file_entry.file_hash not in hash_to_files:
                    hash_to_files[file_entry.file_hash] = []
                hash_to_files[file_entry.file_hash].append(file_entry)

        for dup_group in props.duplicate_groups:
            files = hash_to_files.get(dup_group.hash_value, [])
            if len(files) < 2:
                continue

            canonical = files[0]
            canonical_path = canonical.filepath

            if bpy.data.filepath:
                try:
                    canonical_path = bpy.path.relpath(canonical_path)
                except ValueError:
                    pass

            for dup_file in files[1:]:
                if dup_file.filepath == canonical.filepath:
                    continue
                if apply_new_path(dup_file.name, dup_file.file_type, canonical_path) is not None:
                    consolidated_count += 1

        if consolidated_count > 0:
            self.report({'INFO'}, f"Consolidated {consolidated_count} duplicate references")
            scan_external_files(context)
        else:
            self.report({'INFO'}, "No duplicates to consolidate")

        return {'FINISHED'}


class PROJMAN_UL_files(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            row.prop(item, "selected", text="")

            if not item.exists:
                row.label(text="", icon='ERROR')
            else:
                row.label(text="", icon=TYPE_ICONS.get(item.file_type, 'FILE'))

            row.label(text=item.name)

            if item.exists:
                row.label(text=format_size(item.file_size))
            else:
                row.label(text="MISSING", icon='ERROR')

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE')


class PROJMAN_UL_duplicates(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            row.label(text="", icon=TYPE_ICONS.get(item.file_type, 'FILE'))

            row.label(text=f"{item.file_count}x")

            names = item.file_names
            if len(names) > 40:
                names = names[:37] + "..."
            row.label(text=names)

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='DUPLICATE')


class PROJMAN_PT_main(Panel):
    bl_label = "Project Manifest"
    bl_idname = "PROJMAN_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        layout.label(text="Destination Folder:")
        row = layout.row(align=True)
        row.prop(props, "destination_path", text="")
        row.operator("project_manager.open_destination", text="", icon='FILE_FOLDER')


class PROJMAN_PT_options(Panel):
    bl_label = "Include"
    bl_idname = "PROJMAN_PT_options"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

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
        row.prop(props, "include_sequencer", toggle=True)


class PROJMAN_PT_settings(Panel):
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
    bl_label = "External Files"
    bl_idname = "PROJMAN_PT_files"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        layout.operator("project_manager.scan_files", icon='FILE_REFRESH')

        if props.total_files > 0:
            box = layout.box()
            col = box.column(align=True)
            col.label(text=f"Total Files: {props.total_files}")
            col.label(text=f"Total Size: {format_size(props.total_size)}")
            if props.missing_files > 0:
                col.label(text=f"Missing: {props.missing_files}", icon='ERROR')

        if len(props.external_files) > 0:
            row = layout.row()
            row.template_list(
                "PROJMAN_UL_files", "",
                props, "external_files",
                props, "active_file_index",
                rows=5
            )

            row = layout.row(align=True)
            row.operator("project_manager.select_all", text="All")
            row.operator("project_manager.deselect_all", text="None")

            if props.active_file_index < len(props.external_files):
                active = props.external_files[props.active_file_index]
                layout.label(text=active.filepath, icon='FILE')


class PROJMAN_PT_actions(Panel):
    bl_label = "Collect"
    bl_idname = "PROJMAN_PT_actions"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        selected_count = sum(1 for f in props.external_files if f.selected)
        selected_size = sum(f.file_size for f in props.external_files if f.selected and f.exists)

        if selected_count > 0:
            layout.label(text=f"Selected: {selected_count} files ({format_size(selected_size)})")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("project_manager.collect_files", icon='EXPORT')


class PROJMAN_PT_packing(Panel):
    bl_label = "Pack into .blend"
    bl_idname = "PROJMAN_PT_packing"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        layout.label(text="File Types to Pack:")
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(props, "pack_images", toggle=True)
        row.prop(props, "pack_sounds", toggle=True)
        row.prop(props, "pack_fonts", toggle=True)

        layout.separator()

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("project_manager.pack_all", icon='PACKAGE')
        row.operator("project_manager.unpack_all", icon='UGLYPACKAGE')


class PROJMAN_PT_duplicates(Panel):
    bl_label = "Duplicate Detection"
    bl_idname = "PROJMAN_PT_duplicates"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    bl_parent_id = "PROJMAN_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.project_manager

        layout.operator("project_manager.scan_duplicates", icon='VIEWZOOM')

        if props.duplicate_count > 0:
            box = layout.box()
            col = box.column(align=True)
            col.label(text=f"Duplicate References: {props.duplicate_count}")
            col.label(text=f"Wasted Space: {format_size(props.duplicate_wasted_size)}")

        if len(props.duplicate_groups) > 0:
            row = layout.row()
            row.template_list(
                "PROJMAN_UL_duplicates", "",
                props, "duplicate_groups",
                props, "active_duplicate_index",
                rows=4
            )

            if props.active_duplicate_index < len(props.duplicate_groups):
                active_dup = props.duplicate_groups[props.active_duplicate_index]
                box = layout.box()
                box.label(text="Duplicate files:", icon='INFO')
                for name in active_dup.file_names.split(", "):
                    box.label(text=f"  {name}")

            layout.separator()
            row = layout.row()
            row.scale_y = 1.3
            row.operator("project_manager.consolidate_duplicates", icon='AUTOMERGE_ON')


classes = (
    PROJMAN_ExternalFile,
    PROJMAN_DuplicateGroup,
    PROJMAN_Properties,
    PROJMAN_OT_scan_files,
    PROJMAN_OT_collect_files,
    PROJMAN_OT_select_all,
    PROJMAN_OT_deselect_all,
    PROJMAN_OT_open_destination,
    PROJMAN_OT_pack_all,
    PROJMAN_OT_unpack_all,
    PROJMAN_OT_scan_duplicates,
    PROJMAN_OT_consolidate_duplicates,
    PROJMAN_UL_files,
    PROJMAN_UL_duplicates,
    PROJMAN_PT_main,
    PROJMAN_PT_options,
    PROJMAN_PT_files,
    PROJMAN_PT_settings,
    PROJMAN_PT_actions,
    PROJMAN_PT_packing,
    PROJMAN_PT_duplicates,
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
