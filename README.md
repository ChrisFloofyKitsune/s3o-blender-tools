S3O models are represented in Blender using a "S3O Root" object that sorts properties such as height, collision radius, texture paths
Emit/Aim/Flare Points are represented by a "S3O Aim Point" object

The placeholder empties that visually display the properties of the above can be directly edited and changes will be redirected to the properties in their parent objects.

You must have a S3O Root selected to export the model.
#### Note: _**All rotations and scaling are be baked into the mesh data on export!!**_

Baked Ambient Occlusion data is properly extracted and is imported into a Color Attribute called "ambient_occlusion", allowing direct editing of the AO data via the Vertex Paint tools. (Technically, only the red channel is read on model export)

However, the existing S3O2OBJ tool is still required for baking normals with xNormal