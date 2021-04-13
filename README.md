# MeshTools

This plugin adds several tools for analysis and manipulation of meshes.

The following functions are available through both the `Extensions -> Mesh
Tools` menu and the Mesh Tools submenu of the viewport context menu. These
fuctions require one or more models being selected first.

### Reload model
Reloads the selected model(s) from disk, if the filename is known and the
file still exists.

### Rename model
Changes the name of the model in the "Object List" in the lower left corner
of the viewport. This currently does not work on groups.

### Replace model
Replaces the selected model(s) with a different file. This does not work on
groups, and a single model can only be replaced with a single mesh.

### Check mesh
Checks to see if the model is "watertight", and if it contains separate 
"submodels".

### Analyse mesh
Count the number of vertices and faces of the selected models.

### Fix simple holes
Try to fix simple holes in models to make them "watertight". This is not meant
as an exhaustive way to repair all models. External tools may be necessary to
repair extensively broken models.

### Fix model normals
Recalculate the model normals, so the visualisation of what parts of the model
need support is accurate for models with reversed or invalid normals.

### Split model into parts
When multiple separate bodies are contained within a single mesh, this function
can split them apart so they can be manipulated individually.

### Randomise location
When printing with a consumable build plate surface, it can be beneficial to
print have each print on a different location on the build plate to make sure
it wears down evenly.

### Apply transformations to mesh
This function applies the rotation and scale to the mesh coordinates, and
resets the model rotation and scale to upright and 100%. This can make it
easier to apply scale, and can prevent some manipulation inconsistencies in
Cura (such as the wrong axis scaling when a model is rotated).

### Reset origin to center of mesh
When loading single models into Cura, the origin (the point around which the
model is rotated) is normally reset to the center of the model. Some models
may get a different origin, such as the resulting meshes from the "Split model
into parts" function. It can be convenient to reset the origin to the center
of these parts for further manipulation, but this will make Cura forget about
the original relative position of parts so the "merge" function will no longer
put the parts together properly.

The following options can be set in the settings dialog which can be found via
`Extensions -> Mesh Tools -> Mesh Tools Settings`:

### Check models on load
Automatically check the check models when loading them. In Cura 4.6 and newer
this may lead to double messages that the model needs repair.

### Fix normals on load
Automatically recreate the normals for each loaded model. This can be useful
if you use a modeler that uses a different normal "winding" than Cura, which
causes Cura to show overhangs are needed on top of models.

### Unit for files that don't specify a unit
Automatically scale models that are loaded into Cura if they are exported in
another unit than millimeters. This applies only to mesh files that do not
specify the unit, such as STL, OBJ and PLY.