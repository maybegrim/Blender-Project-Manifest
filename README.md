# Blender Project Manager

A free, open-source Blender extension that collects, consolidates, and archives your Blender projects with all their external assets — inspired by Adobe Premiere Pro's Project Manager.

**Blender 4.2+ | GPL v3 | Free & Open Source**

---

## The Problem

Blender projects often reference dozens of external files scattered across your hard drive:

- Textures in one folder
- HDRIs in another
- Fonts from your system directory
- Sound effects from a sound library
- Linked assets from other .blend files

When you need to **archive a project**, **move it to another machine**, or **share it with a collaborator**, you're left manually hunting for files and hoping you didn't miss any.

## The Solution

**Blender Project Manager** scans your project, finds every external file reference, and collects them all into a single organized folder — with the option to automatically update all the paths in your .blend file.

One click. Done.

---

## Features

### Core Functionality

| Feature | Description |
|---------|-------------|
| **Scan Project** | Detect all external file references in your project |
| **Collect Files** | Copy all assets to a destination folder |
| **Relink Paths** | Automatically update paths in the collected .blend file |
| **Missing File Detection** | Identify broken links before they cause problems |

### Supported Asset Types

- **Images** — Textures, HDRIs, reference images (PNG, JPG, EXR, HDR, TIFF, etc.)
- **Sounds** — Audio files for VSE or speaker objects (WAV, MP3, OGG, FLAC)
- **Fonts** — Font files used by text objects (TTF, OTF)
- **Video Clips** — Movie clips for tracking or compositing
- **Cache Files** — Alembic (.abc) and USD files
- **Volumes** — OpenVDB volumetric data
- **Linked Libraries** — External .blend files

### Options

| Option | Description |
|--------|-------------|
| **Exclude Unused** | Skip assets that aren't actually used in the scene |
| **Flatten Folders** | Put all files in one folder (vs. organized subfolders) |
| **Rename to Match** | Rename files to match their Blender datablock names |
| **Copy .blend File** | Include a copy of your project file |
| **Relink Paths** | Update all paths in the copy to point to the new locations |

### Packing

| Feature | Description |
|---------|-------------|
| **Pack All** | Embed all external files directly into the .blend file |
| **Selective Packing** | Choose which file types to pack (images, sounds, fonts) |
| **Unpack All** | Extract all packed files back to disk |

### Duplicate Detection

| Feature | Description |
|---------|-------------|
| **Find Duplicates** | Scan for identical files referenced multiple times |
| **Consolidate** | Make all duplicate references point to a single file |
| **Wasted Space** | See how much disk space duplicates are wasting |

---

## Installation

### Method 1: Install as Extension (Recommended for Blender 4.2+)

1. Download the latest release (`.zip` file)
2. In Blender, go to **Edit → Preferences → Get Extensions**
3. Click the dropdown arrow → **Install from Disk...**
4. Select the downloaded `.zip` file
5. Enable the extension

### Method 2: Manual Installation

1. Download or clone this repository
2. Copy the `blender_project_manager` folder to your Blender addons directory:
   - **Windows:** `%APPDATA%\Blender Foundation\Blender\4.2\extensions\user_default\`
   - **macOS:** `~/Library/Application Support/Blender/4.2/extensions/user_default/`
   - **Linux:** `~/.config/blender/4.2/extensions/user_default/`
3. Restart Blender and enable in Preferences

---

## Usage

### Quick Start

1. Open your Blender project
2. Go to **Properties → Output Properties**
3. Find the **Project Manager** panel
4. Set a **Destination Folder**
5. Click **Scan Project** to find all external files
6. Review the file list and options
7. Click **Collect Project**

### Step-by-Step Guide

#### 1. Prepare Your Project

Before collecting, make sure your .blend file is saved. The addon uses the saved file's location to resolve relative paths.

#### 2. Choose What to Include

In the **Include** sub-panel, toggle which asset types to collect:

```
[x] Images    [x] Sounds    [x] Fonts
[x] Videos    [x] Caches    [x] Volumes
[x] Libraries
```

#### 3. Configure Settings

In the **Settings** sub-panel:

- **Exclude Unused Data**: Only collect assets that are actually used
- **Flatten Folder Structure**: Put everything in one folder instead of organized subfolders
- **Rename to Match Datablock**: Rename `IMG_4032.jpg` to `Wood_Texture.jpg`
- **Copy .blend File**: Include your project file in the collection
- **Relink Paths**: Update paths in the copy so it's fully portable

#### 4. Scan and Review

Click **Scan Project** to analyze your file. You'll see:

- Total number of external files
- Total size on disk
- Any missing files (shown with error icons)

The file list shows each asset with:
- Checkbox to include/exclude
- Type icon
- Asset name
- File size

#### 5. Collect

Click **Collect Project** to copy everything to your destination.

The resulting folder structure (with default settings):

```
MyProject_Collected/
├── MyProject.blend
├── textures/
│   ├── wood_diffuse.jpg
│   ├── metal_normal.png
│   └── environment.hdr
├── sounds/
│   └── ambient.wav
├── fonts/
│   └── Roboto-Regular.ttf
├── videos/
│   └── footage.mp4
├── caches/
│   └── simulation.abc
├── volumes/
│   └── smoke.vdb
└── libraries/
    └── asset_library.blend
```

---

## Use Cases

### Archiving Completed Projects

Store everything needed to reopen the project years from now, even if your asset library changes.

### Sending to Render Farm

Package your project so render nodes can find all assets without manual path fixing.

### Collaborating with Others

Share a fully self-contained project folder that works immediately on any machine.

### Moving Between Computers

Transfer projects between your workstation and laptop without broken links.

### Backing Up Client Work

Create clean archives of client projects for long-term storage.

---

## Technical Details

### How Path Resolution Works

Blender stores file paths in several ways:

1. **Absolute paths**: `/Users/name/textures/wood.jpg`
2. **Relative paths**: `//textures/wood.jpg` (relative to .blend location)

The addon:
1. Resolves all paths to absolute paths
2. Copies files to the destination
3. Converts paths back to relative (e.g., `//textures/wood.jpg`)

This ensures the collected project works regardless of where it's stored.

### Handling Duplicate Filenames

If two assets have the same filename (e.g., `texture.png` from different folders), the addon automatically adds a numeric suffix: `texture.png`, `texture_1.png`.

### Packed Files

Files that are already packed into the .blend (embedded) are skipped — they're already portable.

---

## Roadmap

Planned features for future releases:

- [ ] **Sequence Support** — Handle image sequences intelligently
- [ ] **Transcode Option** — Convert videos to a consistent format
- [ ] **CLI Mode** — Run collection from command line for batch processing

---

## Requirements

- **Blender 4.2** or newer
- **Operating System**: Windows, macOS, or Linux

---

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report Bugs**: Open an issue describing the problem
2. **Suggest Features**: Share ideas for improvements
3. **Submit Code**: Fork the repo and create a pull request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/maybegrim/Blender-Project-Manager.git

# Create a symlink to your Blender extensions folder (example for Windows)
mklink /D "%APPDATA%\Blender Foundation\Blender\4.2\extensions\user_default\blender_project_manager" "path\to\repo\blender_project_manager"
```

### Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Document complex logic with comments
- Test changes with various project types

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

This means you're free to:
- Use the addon for any purpose
- Modify the source code
- Share the addon with others
- Distribute modified versions

---

## Acknowledgments

- Inspired by Adobe Premiere Pro's Project Manager feature
- Built for the Blender community
- Special thanks to everyone who contributes to Blender's open-source ecosystem

---

## Support

If you find this addon useful, consider:

- Starring the repository
- Sharing it with other Blender users
- Contributing improvements
- Reporting bugs and suggestions

**This addon is and always will be free.**

---

*Made with care for the Blender community.*
