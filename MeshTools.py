# Copyright (c) 2018 fieldOfView
# MeshTools is released under the terms of the AGPLv3 or higher.

from PyQt5.QtCore import QObject

import numpy
import trimesh

from UM.Extension import Extension
from UM.Application import Application
from UM.Message import Message

from UM.Scene.Selection import Selection
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from UM.Mesh.MeshData import MeshData, calculateNormalsFromIndexedVertices
from UM.Mesh.MeshBuilder import MeshBuilder

from cura.Scene.CuraSceneNode import CuraSceneNode

from .SetTransformMatrixOperation import SetTransformMatrixOperation

from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

class MeshTools(Extension, QObject,):
    def __init__(self, parent = None):
        QObject.__init__(self, parent)
        Extension.__init__(self)

        self._controller = Application.getInstance().getController()

        self.addMenuItem(catalog.i18nc("@item:inmenu", "Check models"), self.checkSelectedMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix simple holes"), self.fixSimpleHolesForSelectedMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix model normals"), self.fixNormalsForSelectedMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Split model into parts"), self.splitSelectedMeshes)

        self._message = Message(title=catalog.i18nc("@info:title", "Mesh Tools"))

    def checkSelectedMeshes(self):
        message_body = catalog.i18nc("@info:status", "Model summary:")
        for node in Selection.getAllSelectedObjects():
            tri_node = self._toTriMesh(node.getMeshData())
            message_body = message_body + "\n - %s:" % node.getName()
            if tri_node.is_watertight:
                message_body = message_body + " " + catalog.i18nc("@info:status", "is watertight")
            else:
                message_body = message_body + " " + catalog.i18nc("@info:status", "is NOT watertight")
            if tri_node.body_count > 1:
                message_body = message_body + " " + catalog.i18nc("@info:status", "and consists of {body_count} submeshes").format(body_count = tri_node.body_count)

        self._message.setText(message_body)
        self._message.show()

    def fixSimpleHolesForSelectedMeshes(self):
        for node in Selection.getAllSelectedObjects():
            tri_node = self._toTriMesh(node.getMeshData())
            success = tri_node.fill_holes()
            self._replaceSceneNode(node, [tri_node])
            if not success:
                self._message.setText(catalog.i18nc("@info:status", "The mesh needs more extensive repair to become watertight"))
                self._message.show()

    def fixNormalsForSelectedMeshes(self):
        for node in Selection.getAllSelectedObjects():
            tri_node = self._toTriMesh(node.getMeshData())
            tri_node.fix_normals()
            self._replaceSceneNode(node, [tri_node])

    def splitSelectedMeshes(self):
        for node in Selection.getAllSelectedObjects():
            tri_node = self._toTriMesh(node.getMeshData())
            if tri_node.body_count > 1:
                self._replaceSceneNode(node, tri_node.split())

    def _replaceSceneNode(self, existing_node, trimeshes):
        name = existing_node.getName()
        file_name = existing_node.getMeshData().getFileName()
        transformation = existing_node.getWorldTransformation()
        parent = existing_node.getParent()
        extruder_id = existing_node.callDecoration("getActiveExtruder")
        build_plate = existing_node.callDecoration("getBuildPlateNumber")

        op = GroupedOperation()
        op.addOperation(RemoveSceneNodeOperation(existing_node))

        for i, tri_node in enumerate(trimeshes):
            mesh_data = self._toMeshData(tri_node)

            new_node = CuraSceneNode()
            new_node.setSelectable(True)
            new_node.setMeshData(mesh_data)
            new_node.callDecoration("setActiveExtruder", extruder_id)
            new_node.addDecorator(BuildPlateDecorator(build_plate))
            new_node.addDecorator(SliceableObjectDecorator())

            op.addOperation(AddSceneNodeOperation(new_node, parent))
            op.addOperation(SetTransformMatrixOperation(new_node, transformation))

        op.push()

    def _toTriMesh(self, mesh_data: MeshData) -> trimesh.base.Trimesh:
        return trimesh.base.Trimesh(vertices=mesh_data.getVertices(), faces=mesh_data.getIndices(), vertex_normals=mesh_data.getNormals())

    def _toMeshData(self, tri_node: trimesh.base.Trimesh) -> MeshData:
        tri_faces = tri_node.faces
        tri_vertices = tri_node.vertices

        indices = []
        vertices = []

        index_count = 0
        face_count = 0
        for triface in tri_faces:
            face = []
            for triindex in triface:
                vertices.append(tri_vertices[triindex])
                face.append(index_count)
                index_count = index_count + 1
            indices.append(face)
            face_count = face_count + 1

        vertices = numpy.asarray(vertices, dtype=numpy.float32)
        indices = numpy.asarray(indices, dtype=numpy.int32)
        normals = calculateNormalsFromIndexedVertices(vertices, indices, face_count)

        mesh_data = MeshData(vertices=vertices, indices=indices, normals=normals)
        return mesh_data
