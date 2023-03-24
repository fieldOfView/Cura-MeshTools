# Copyright (c) 2023 Aldo Hoeben / fieldOfView.
# MeshTools is released under the terms of the AGPLv3 or higher.

from UM.Operations.SetTransformOperation import SetTransformOperation
from UM.Operations.Operation import Operation
from UM.Math.Matrix import Matrix
from UM.Math.Vector import Vector

from typing import Union

##  Operation that translates, rotates and scales a node all at once.
class SetTransformMatrixOperation(SetTransformOperation):
    ##  Creates the transform operation.
    #
    #   \param node The scene node to transform.
    #   \param transform A fully formed transformation matrix to transform the node with.
    def __init__(self, node, transform = None) -> None:
        super().__init__(node)

        self._old_transformation = node.getWorldTransformation()
        self._new_transformation = transform

    ##  Merges this operation with another SetTransformMatrixOperation.
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
        if type(other) is not SetTransformMatrixOperation:
            return False
        if other._node != self._node: # Must be on the same node.
            return False

        op = SetTransformMatrixOperation(self._node)
        op._old_transformation = other._old_transformation
        op._new_transformation = self._new_transformation
        return op

    ##  Returns a programmer-readable representation of this operation.
    #
    #   A programmer-readable representation of this operation.
    def __repr__(self) -> str:
        return "SetTransformMatrixOperation(node = {0})".format(self._node)
