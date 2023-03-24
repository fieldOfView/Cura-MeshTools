# Copyright (c) 2023 Aldo Hoeben / fieldOfView.
# MeshTools is released under the terms of the AGPLv3 or higher.

from UM.Operations.Operation import Operation
from UM.Mesh.MeshData import MeshData
from UM.Scene.SceneNode import SceneNode

from typing import Union

##  Operation that replaces the meshdata of a node.
class SetMeshDataAndNameOperation(Operation):
    ##  Creates the transform operation.
    #
    #   \param node The scene node to transform.
    #   \param transform A fully formed transformation matrix to transform the node with.
    def __init__(self, node: SceneNode, mesh_data: MeshData, name: str = "") -> None:
        super().__init__()

        self._node = node

        self._old_mesh_data = node.getMeshData()
        self._old_name = node.getName()

        self._new_mesh_data = mesh_data
        self._new_name = name

        if mesh_data.getVertices != None:
            self.redo()

    ##  Undoes the mesh data change, restoring the node to the old state.
    def undo(self) -> None:

        self._node.setMeshData(self._old_mesh_data)
        self._node.setName(self._old_name)

    ##  Re-applies the mesh data change after it has been undone.
    def redo(self) -> None:

        self._node.setMeshData(self._new_mesh_data)
        self._node.setName(self._new_name)

    ##  Merges this operation with another SetMeshDataAndNameOperation.
    #
    #   This prevents the user from having to undo multiple operations if they
    #   were not his operations.
    #
    #   You should ONLY merge this operation with an older operation. It is NOT
    #   symmetric.
    #
    #   \param other The older operation with which to merge this operation.
    #   \return A combination of the two operations, or False if the merge
    #   failed.
    def mergeWith(self, other) -> Union[Operation, bool]:
        if type(other) is not SetMeshDataAndNameOperation:
            return False
        if other._node != self._node: # Must be on the same node.
            return False

        op = SetMeshDataAndNameOperation(self._node, MeshData())
        op._old_mesh_data = other._old_mesh_data
        op._old_name = other._old_name
        op._new_mesh_data = self._new_mesh_data
        op._new_name = self._new_name

        return op

    ##  Returns a programmer-readable representation of this operation.
    #
    #   A programmer-readable representation of this operation.
    def __repr__(self) -> str:
        return "SetMeshDataAndNameOperation(node = {0})".format(self._node)
