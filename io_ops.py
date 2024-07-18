import os.path
from enum import Enum

import bpy
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator, Context, Menu, Event, Material, Object
from bpy_extras.io_utils import ImportHelper, ExportHelper
from . import s3o, s3o_utils, util, obj_props
from .obj_props import S3ORootProperties


class ImportSpring3dObject(Operator, ImportHelper):
    """Import from a *.s3o file"""
    bl_idname = "s3o_tools.import_s3o"
    bl_label = "Spring/Recoil (*.s3o)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".s3o"

    filter_glob: StringProperty(
        default="*.s3o",
        options={'HIDDEN'},
        maxlen=255
    )

    merge_vertices: BoolProperty(
        name="Merge Vertices",
        description="Merge Vertices that share the same position",
        default=True,
    )

    unit_textures_folder: StringProperty(
        name="Unit Textures Folder",
        description="Location of the unit textures."
                    "Leave blank to let the importer search for it automatically",
        default="",
        subtype="DIR_PATH",
    )

    @staticmethod
    def menu_func(menu: Menu, context: Context):
        menu.layout.operator(ImportSpring3dObject.bl_idname)

    def execute(self, context: Context) -> set[str]:
        if bpy.context.active_object:
            bpy.ops.object.mode_set(mode='OBJECT')

        with open(self.filepath, 'rb') as s3o_file:
            s3o_data = s3o.S3O.from_bytes(s3o_file.read())
        s3o_data.triangulate_faces()

        obj_name = bpy.path.display_name_from_filepath(self.filepath)
        obj = s3o_utils.s3o_to_blender_obj(
            s3o_data,
            name=obj_name,
            merge_vertices=self.merge_vertices
        )

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        if self.unit_textures_folder == '':
            search_path = os.path.split(self.filepath)[0]
            attempts_left = 4
            while attempts_left > 0:
                if os.path.exists(tex_dir := os.path.join(search_path, 'unittextures')):
                    ImportTexturesExec.parent_operator = self
                    bpy.ops.s3o_tools.import_textures_exec(
                        directory=tex_dir,
                        set_globally=False,
                    )
                    break
                search_path = os.path.split(search_path)[0]
                attempts_left -= 1

        return {'FINISHED'}


class ExportSpring3dObject(Operator, ExportHelper):
    """Export a S3O Root Object a *.s3o file"""
    bl_idname = "s3o_tools.export_s3o"
    bl_label = "Spring/Recoil (*.s3o)"
    bl_options = {'REGISTER'}

    filename_ext = ".s3o"

    filter_glob: StringProperty(
        default="*.s3o",
        options={'HIDDEN'},
        maxlen=255,
    )

    @staticmethod
    def get_s3o_to_export(context: Context) -> S3ORootProperties:
        s3o_roots_in_scene = [o.s3o_root for o in context.scene.objects if S3ORootProperties.poll(o)]
        if len(s3o_roots_in_scene) == 1:
            return s3o_roots_in_scene[0]
        else:
            return obj_props.get_s3o_root_object(context.object).s3o_root

    @staticmethod
    def menu_func(menu: Menu, context: Context):
        menu.layout.operator(ExportSpring3dObject.bl_idname)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return (sum(1 for o in context.scene.objects if S3ORootProperties.poll(o)) == 1
                or obj_props.get_s3o_root_object(context.object) is not None)

    def invoke(self, context: Context, event: Event) -> set[str]:
        self.filepath = self.get_s3o_to_export(context).s3o_name + self.filename_ext
        return super().invoke(context, event)

    def execute(self, context: Context) -> set[str]:
        s3o_obj = self.get_s3o_to_export(context).id_data
        s3o_data = s3o_utils.blender_obj_to_s3o(s3o_obj)
        data = s3o_data.serialize()
        with open(self.filepath, 'wb') as output:
            print(f'Writing {len(data)} bytes to {self.filepath}')
            output.write(data)

        return {'FINISHED'}


class ImportTextures(Operator):
    """Select folder to import textures from"""
    bl_idname = "s3o_tools.import_textures"
    bl_label = "Import Textures"
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(
        name="Textures Folder Path",
        description="Folder to look for textures in",
        subtype='DIR_PATH',
    )

    filter_folder: BoolProperty(
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'},
        name="",
        description="Show folders in the File Browser",
    )

    set_globally: BoolProperty(
        name="Load Textures Globally",
        description="If false, only loads for selection. If true, loads for all s3o root objects in the scene.",
        default=True,
    )

    @classmethod
    def poll(cls, context: Context):
        return any(S3ORootProperties.poll(o) for o in bpy.context.scene.objects)

    def invoke(self, context: Context, event: Event) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context) -> set[str]:
        ImportTexturesExec.parent_operator = self
        bpy.ops.s3o_tools.import_textures_exec(
            directory=self.directory,
            set_globally=self.set_globally
        )
        return {'FINISHED'}


class AddonAsset(tuple[str, str], Enum):
    NodesSampler = ('node_groups', 'BARLikeSampling')
    NodesTrackLooper = ('node_groups', 'TrackLooper')
    MaterialTemplate = ('materials', 'Template Material')
    MaterialArmada = ('materials', 'Armada Atlas')
    MaterialCortex = ('materials', 'Cortex Atlas')
    MaterialLegion = ('materials', 'Legion Atlas')

    @property
    def collection_name(self):
        return self[0]

    @property
    def asset_name(self):
        return self[1]


class ImportTexturesExec(Operator):
    bl_idname = "s3o_tools.import_textures_exec"
    bl_label = "Import Textures Exec"
    bl_options = {'INTERNAL'}

    directory: StringProperty(default='')
    set_globally: BoolProperty(default=False)

    parent_operator: Operator = None

    @staticmethod
    def ensure_assets_loaded(*assets: AddonAsset) -> dict[AddonAsset, any]:
        asset_info = [
            (getattr(bpy.data, asset.collection_name), asset)
            for asset in assets
        ]

        assets_to_load: list[tuple[any, AddonAsset]] = [
            (collection, asset) for (collection, asset) in asset_info
            if (
                asset.asset_name not in collection
                or collection[asset.asset_name] is None
                or collection[asset.asset_name].is_missing
            )
        ]

        if len(assets_to_load) != 0:
            # clean up any broken assets
            for (data, asset) in assets_to_load:
                if asset.asset_name in data:
                    data.remove(data[asset.asset_name])

            with util.library_load_addon_assets() as (_, data_to):
                for _, asset in assets_to_load:
                    names_to_load = getattr(data_to, asset.collection_name, list())
                    names_to_load.append(asset.asset_name)
                    setattr(data_to, asset.collection_name, names_to_load)

        return {asset: collection[asset.asset_name] for (collection, asset) in asset_info}

    def load_materials_for_obj(self, root_obj: Object, context: Context):
        D = bpy.data

        root_props: S3ORootProperties = root_obj.s3o_root

        material_to_load = AddonAsset.MaterialTemplate
        if root_props.s3o_name.startswith('arm'):
            material_to_load = AddonAsset.MaterialArmada
        elif root_props.s3o_name.startswith('cor'):
            material_to_load = AddonAsset.MaterialCortex
        elif root_props.s3o_name.startswith('leg'):
            material_to_load = AddonAsset.MaterialLegion

        new_mat_name = root_props.s3o_name + '.material'
        new_mat: Material | None = None
        if new_mat_name in D.materials:
            new_mat: Material = D.materials[new_mat_name]

            if (new_mat is not None and (
                new_mat.is_missing
                or AddonAsset.NodesSampler.asset_name not in new_mat.node_tree.nodes
                or new_mat.node_tree.nodes[AddonAsset.NodesSampler.asset_name].node_tree.is_missing
                or AddonAsset.NodesTrackLooper.asset_name not in new_mat.node_tree.nodes
                or new_mat.node_tree.nodes[AddonAsset.NodesTrackLooper.asset_name].node_tree.is_missing
            )):
                D.materials.remove(new_mat)
                new_mat = None

        if new_mat is None:
            template_mat = self.ensure_assets_loaded(material_to_load)[material_to_load]
            new_mat = template_mat.copy()
            new_mat.name = new_mat_name

            if material_to_load == AddonAsset.MaterialTemplate:
                if self.directory != '':
                    print(f'Attempting to load textures from: {self.directory}')
                    try:
                        tex1 = D.images.load(
                            os.path.join(self.directory, root_props.texture_path_1), check_existing=True
                        )
                        tex1.alpha_mode = 'CHANNEL_PACKED'
                        new_mat.node_tree.nodes['Color Texture'].image = tex1

                        tex2 = D.images.load(
                            os.path.join(self.directory, root_props.texture_path_2), check_existing=True
                        )
                        tex2.colorspace_settings.is_data = True
                        new_mat.node_tree.nodes['Shader Texture'].image = tex2

                        if (common_prefix := os.path.commonprefix(
                            [root_props.texture_path_1, root_props.texture_path_2]
                        )) != '':
                            try:
                                normal_tex = D.images.load(
                                    os.path.join(
                                        self.directory,
                                        f'{common_prefix}normal{os.path.splitext(tex1.filepath)[1]}'
                                    ),
                                    check_existing=True
                                )
                                normal_tex.colorspace_settings.is_data = True
                                new_mat.node_tree.nodes['Normal Texture'].image = normal_tex
                            except Exception:
                                self.parent_operator.report(
                                    {'WARNING'},
                                    f'Could not automatically find the Normal texture for "{root_props.s3o_name}"!'
                                )
                    except Exception as err:
                        self.parent_operator.report({'ERROR'}, 'Could not set up the textures :(')
                        raise err

        if material_to_load != AddonAsset.MaterialTemplate:
            self.parent_operator.report(
                {"INFO"}, f'Loaded premade material "{material_to_load.asset_name}" from addon assets!'
            )
        else:
            self.parent_operator.report({"INFO"}, f'Created material from textures in {self.directory}')

        for child_obj in root_obj.children_recursive:
            child_obj.active_material = new_mat

    def execute(self, context: Context) -> set[str]:
        if self.set_globally:
            targets = set(o for o in context.scene.objects if S3ORootProperties.poll(o))
        else:
            targets = set(obj_props.get_s3o_root_object(o) for o in context.selected_objects)
        if len(targets) == 0:
            return {'CANCELED'}

        self.ensure_assets_loaded(AddonAsset.NodesSampler, AddonAsset.NodesTrackLooper)

        for root_obj in targets:
            self.load_materials_for_obj(root_obj, context)

        return {'FINISHED'}


def register():
    bpy.utils.register_class(ImportSpring3dObject)
    bpy.utils.register_class(ExportSpring3dObject)
    bpy.utils.register_class(ImportTextures)
    bpy.utils.register_class(ImportTexturesExec)

    bpy.types.TOPBAR_MT_file_import.append(ImportSpring3dObject.menu_func)
    bpy.types.TOPBAR_MT_file_export.append(ExportSpring3dObject.menu_func)


def unregister():
    bpy.utils.unregister_class(ImportSpring3dObject)
    bpy.utils.unregister_class(ExportSpring3dObject)
    bpy.utils.unregister_class(ImportTextures)
    bpy.utils.unregister_class(ImportTexturesExec)

    bpy.types.TOPBAR_MT_file_import.remove(ImportSpring3dObject.menu_func)
    bpy.types.TOPBAR_MT_file_export.remove(ExportSpring3dObject.menu_func)
