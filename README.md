# s3o Blender Tools

Small collection of tools for working with Spring/Recoil .s3o 3D model files in Blender.

# Install instructions

1. Go over to the [Releases](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/releases) page and download the latest .zip file.
2. Make sure you are on Blender 4.1 or later. https://www.blender.org/download/
3. In the top left toolbar, open the "Edit" menu and click "Preferences"

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/06e93d8a-767b-4aef-94a0-ce29b2ea9e46)

4. Inside the Preferences window, go the "Add-ons" tab, then click Install

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/04433979-8856-42ce-84a2-9a6cf4f8b279)

5. This will open a File Menu. Go to where you downloaded the s3o Tools zip file and then click "Install Add-on"
6. After that, the Add-ons tab will change to show the newly installed addon with a grayed out label reading "Import-Export: Spring 3D Object (*.s3o) Tools".
   Click the checkbox on the side of the label to enable s3o Tools. Now you can close the Preferences window.

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/f0210c53-7cde-4d81-bf61-fe420e27e1fa)

8. In the 3D Viewport, there should be a new "S3O" tab on the right sidebar.
   If you do not see it, hover your mouse over the 3D View and hit "N" on your keyboard to open up the sidebar (or click the tiny little arrow in the top right of the 3D view).

# Using s3o Tools

Inside the S3O Tab there are a couple of menus.

## Menus

### !! Read the Tooltips !!
Hover over each and every option to get a description of what it does.

### S3O Tools Menu
The S3O Tools menu has the general tools for use in editing/creating models.

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/c6a04966-0265-4431-a872-579e66f312c6)

### Ambient Occlusion
The Ambient Occlusion menu is used for baking Ambient Occlusion (AO)- either into the model's vertices or into a baseplate image (for buildings).

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/e5943569-714f-4047-a953-3449f33fa3a9)

# S3O Objects


## Placeholders

The placeholder empties that visually display the properties of these special objects can be directly edited and changes will be applied to the setting in the S3O objects.

Details are in the entries for each object type.

## S3O Root

s3o models are represented in Blender using a "S3O Root" object that sorts properties such as height, collision radius, texture paths

**You must have a S3O Root in the scene to be able to export the model.**

### Properties
* Name: name of the model. Automatically set on Import and used to name the Export files.
* Collision Radius, Height, Midpoint: These are important use in game. (Linky to docs explaining these soon)
* Color Texture / Other Texture: The name of the textures the model uses. These are used in game and by s3o Tools to locate the texture atlases for the model.
  * Examples: "arm_color.dds"/"arm_other.dds", "cor_color.dds"/"cor_other.dds", "leg_color.dds"/"leg_shader.dds"

![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/34da3f52-8ada-4d34-89f8-555dad38a261)
 ![image](https://github.com/ChrisFloofyKitsune/s3o-blender-tools/assets/4379469/a73fc95b-e778-49d5-bd0e-f56faef73e4f)

#### Placeholders
* The position of the Root object is represented by a set of XYZ axes.
  * Note that the Y axis is pointing up and the Z axis is pointing forwards. These represent what the directions will be once the model is exported
* The Midpoint + Collsion Radius are represented by a sphere
* Height parameter is represented by a circle.

## Aim Point
Emit/Aim/Flare Points are represented by a "S3O Aim Point" object
Placeholders:
* The location of the Aim Point object is a small sphere.
* The Emit Direction and Position are represented by an Arrow.


Note: All rotations and scaling are be baked into the mesh data on export!!

S3O Root objects are rotated such that the local axes match with the S3O model axes. You can technically apply transform rotations to it, but I don't recommend it.

Baked Ambient Occlusion data is properly extracted and is imported into a Color Attribute called "ambient_occlusion", allowing direct editing of the AO data via the Vertex Paint tools. (Technically, only the red channel is read on model export)

"Add Mesh as Child" button that adds a Mesh as a child of the active object
"S3Oify Object Hierarchy" button that prepares an existing model for export / use with this Addon

v0.2.0: Full Ambient Occlusion baking toolset, check tooltips for info. Should have all the AO-related functionality that OBJ2S3O did... save for batch baking.
v0.2.1: AO baking plates are centered under the model. Errors on model import/export.
v0.2.2: Ensure 'ambient_occlusion' attribute exists before baking to it. Tweak AO settings min/max. Improved building groundplate AO edge smoothing.
