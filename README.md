# s3o Blender Tools

Small collection of tools for working with Spring/Recoil .s3o 3D model files in Blender.
The tools are currently designed around making models for Beyond All Reason- though it should work for other games.

# Credits

A big thanks to Beherith who's code I based this off of and ported into Blender.
Equally big thanks to the Beyond All Reason community for making awesome models- making me see the need make this. (The tools available before this were really bad okay)

# Install instructions

1. Go over to the [Releases](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/releases) page and download the latest .zip file.
2. Make sure you are on Blender 4.1 or later. https://www.blender.org/download/
3. You will also want to download the models (and source code and stuff) from the [Beyond All Reason GitHub repo](https://github.com/beyond-all-reason/Beyond-All-Reason)
   * Or for whatever game you are making models for...
4. In the top left toolbar, open the "Edit" menu and click "Preferences"
5. Inside the Preferences window, go the "Add-ons" tab, then click Install

<img width="30%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/06e93d8a-767b-4aef-94a0-ce29b2ea9e46">
<img width="50%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/04433979-8856-42ce-84a2-9a6cf4f8b279">

6. This will open a File Menu. Go to where you downloaded the s3o Tools zip file and then click "Install Add-on"
7. After that, the Add-ons tab will change to show the newly installed addon with a grayed out label reading "Import-Export: Spring 3D Object (*.s3o) Tools".
   * Click the checkbox on the side of the label to enable s3o Tools. Now you can close the Preferences window.
8. In the 3D Viewport, there should be a new "S3O" tab on the right sidebar.
   * If you do not see it, hover your mouse over the 3D View and hit "N" on your keyboard to open up the sidebar (or click the tiny little arrow in the top right of the 3D view).

<img width="50%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/f0210c53-7cde-4d81-bf61-fe420e27e1fa">
<img width="40%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/732c4d80-3c52-4c7f-8748-f6ac3726d0d7">

# Using s3o Tools

Inside the S3O Tab there are a couple of menus.

<img align="right" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/e5943569-714f-4047-a953-3449f33fa3a9">
<img align="right" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/c6a04966-0265-4431-a872-579e66f312c6">

## Menus

### !! Read the Tooltips !!
Hover over each and every option to get a description of what it does.

### S3O Tools Menu
The S3O Tools menu has the general tools for use in editing/creating models.

### Ambient Occlusion
The Ambient Occlusion menu is used for baking Ambient Occlusion (AO)- either into the model's vertices or into a baseplate image (for buildings).

# Import / Export
### Importing

If you are importing from the Beyond All Reason files, the textures should be loaded and the Blender Materials set up automatically.
If not, you can click on the Import Textures button and select the folder in which the textures can be found.

### Exporting

Two big things to note right off:
1. You must have a S3O Root in the scene to be able to export the model.
2. All rotations and scaling are be baked into the mesh data on export!

The model will be also triangulated on export so you probably want to keep a .blend file backup for those nice quads and fancy n-gons.

# S3O Objects
## Placeholders

The placeholder empties that visually display the properties of these special objects can be directly edited and changes will be applied to the setting in the S3O objects.

Details are in the entries for each object type.

## S3O Root

s3o models are represented in Blender using a "S3O Root" object that sorts properties such as height, collision radius, texture paths


### Properties
* Name: name of the model. Automatically set on Import and used to name the Export files.
* Collision Radius, Height, Midpoint: These are important use in game. (Linky to docs explaining these soon)
* Color Texture / Other Texture: The name of the textures the model uses. These are used in game and by s3o Tools to locate the texture atlases for the model.
  * Examples: "arm_color.dds"/"arm_other.dds", "cor_color.dds"/"cor_other.dds", "leg_color.dds"/"leg_shader.dds"

<img width="40%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/3a7e0c52-a93d-42c0-941b-bc6548352508">
<img width="50%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/fb99051e-cec5-44c2-a36a-a99cc9d3e92f">

#### Placeholders
* The position of the Root object is represented by a set of XYZ axes.
  * Note that the Y axis is pointing up and the Z axis is pointing forwards. These represent what the directions will be once the model is exported
* The Midpoint + Collsion Radius are represented by a sphere
* Height parameter is represented by a circle.

## Aim Point
Emit/Aim/Flare Points are represented by a "S3O Aim Point" object
Usually these are left pointing straight forwards since the model and any guns face forwards.

### Properties
* Aim Position/Direction: These control where effects, bullets, smoke, etc spawn and what direction they are to initially move in.
* Align Direction to Rotation: **\[s3o Tools only\]** Toggle this to make the Aim Direction follow the Aim Point's rotation in Blender

<img width="50%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/7af6a8a4-590e-471c-8d19-5c366f23efb6">
<img width="40%" src="https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/8597e19a-ce57-4fdb-afb4-ca7a64abe29e">

#### Placeholders
* The location of the Aim Point object is a small sphere.
* The Emit Direction and Position are represented by an Arrow.

# Ambient Occlusion

Baked Ambient Occlusion data is properly extracted and is imported into a Color Attribute called "ambient_occlusion", allowing direct editing of the AO data via the Vertex Paint tools.

Check out the tooltips for descriptions on what each button and option in the menu does.

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/b794ed69-d903-4986-83a6-a601b9308891)

### Change Log
* v0.1.0: Initial Release
* v0.1.1: Add the "Add Mesh as Child" and "S3Oify Object Hiearchy" buttons.
* v0.2.0: Full Ambient Occlusion baking toolset, check tooltips for info. Should have all the AO-related functionality that OBJ2S3O did... save for batch baking.
* v0.2.1: AO baking plates are centered under the model. Fix errors on model import/export.
* v0.2.2: Ensure 'ambient_occlusion' attribute exists before baking to it. Tweak AO settings min/max. Improved building groundplate AO edge smoothing.
* v0.2.3 Changes:
  * Add new "Min Distance" feature to the Vertex AO baking. It attempts to remove black spots caused by things such as intersecting faces and smooths out the end result.
  * Add Apply Rotation/Scale/Modifiers options to the S3Oify Object Hierarchy tool.
* v0.2.4 Changes: Improve AO baking result a bit more by making a copy of the mesh and splitting it across the sharp edges before baking-- then saving results to the original mesh.
* v0.2.5 Changes: Fix incorrect determination of sharp edges on s3o import.
