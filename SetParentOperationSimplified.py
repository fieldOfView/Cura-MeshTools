# Copyright (c) 2023 Aldo Hoeben / fieldOfView.
# MeshTools is released under the terms of the AGPLv3 or higher.

from cura.Operations.SetParentOperation import SetParentOperation

from UM.Scene.SceneNode import SceneNode

##  Operation that parents a scene node to another scene node without changing the transformation of the node.
class SetParentOperationSimplified(SetParentOperation):

    ##  Sets the parent of the node without applying transformations to the world-transform of the node
    #
    #   \param new_parent The new parent. Note: this argument can be None, which would hide the node from the scene.
    def _set_parent(self, new_parent: SceneNode) -> None:
        self._node.setParent(new_parent)

    ##  Returns a programmer-readable representation of this operation.
    #
    #   A programmer-readable representation of this operation.
    def __repr__(self) -> str:
        return "SetParentOperationSimplified(node = {0})".format(self._node)
