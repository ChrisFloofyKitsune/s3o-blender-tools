import warnings

import bpy
from bpy.types import DepsgraphUpdate
from .s3o_props import S3ORootProperties, S3OAimPointProperties, S3OPlaceholderProperties

responding_to_depsgraph = False
insanity_counter = 0


@bpy.app.handlers.persistent
def s3o_placeholder_depsgraph_listener(*_):
    depsgraph = bpy.context.evaluated_depsgraph_get()

    global insanity_counter
    global responding_to_depsgraph
    if responding_to_depsgraph:
        return

    try:
        if insanity_counter != 0:
            warnings.warn_explicit(f's3o props depsgraph listener has looped {insanity_counter} times!!')
            print(f's3o props depsgraph listener has looped {insanity_counter} times!!')

        insanity_counter += 1
        responding_to_depsgraph = True

        updates: list[DepsgraphUpdate] = list(iter(depsgraph.updates))
        if len(updates) == 0:
            return

        # did the updates start with a placeholder object being modified?
        if S3OPlaceholderProperties.poll(updates[0].id):
            obj = updates[0].id.original
            parent = obj.parent
            tag = obj.s3o_placeholder.tag

            if S3ORootProperties.poll(parent) and not parent.s3o_root.being_updated:
                parent.s3o_root.update_from_placeholder(tag, obj)
            elif S3OAimPointProperties.poll(parent) and not parent.s3o_aim_point.being_updated:
                parent.s3o_aim_point.update_from_placeholder(tag, obj)

        # any root objects?
        for root_obj in (u.id.original for u in updates if S3ORootProperties.poll(u.id)):
            root_props: S3ORootProperties = root_obj.s3o_root
            if not root_props.being_updated:
                root_props.update(None)

        # any aim points?
        for aim_point_obj in (u.id.original for u in updates if S3OAimPointProperties.poll(u.id)):
            ap_props: S3OAimPointProperties = aim_point_obj.s3o_aim_point
            if not ap_props.being_updated:
                ap_props.update(None)

    finally:
        insanity_counter -= 1
        responding_to_depsgraph = False


def register():
    bpy.app.handlers.depsgraph_update_post.append(s3o_placeholder_depsgraph_listener)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(s3o_placeholder_depsgraph_listener)
