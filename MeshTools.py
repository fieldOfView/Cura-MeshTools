# Copyright (c) 2018 fieldOfView
# MeshTools is released under the terms of the AGPLv3 or higher.

from PyQt5.QtCore import QObject

import os.path
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

        self._application = Application.getInstance()
        self._controller = self._application.getController()

        self._application.fileLoaded.connect(self._onFileLoaded)
        self._application.fileCompleted.connect(self._onFileCompleted)
        self._controller.getScene().sceneChanged.connect(self._onSceneChanged)

        self._currently_loading_files = [] #type: List[str]
        self._check_node_queue = [] #type: List[SceneNode]
        self._mesh_not_watertight_messages = {} #type: Dict[str, Message]

        self.addMenuItem(catalog.i18nc("@item:inmenu", "Check models"), self.checkSelectedMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix simple holes"), self.fixSimpleHolesForSelectedMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix model normals"), self.fixNormalsForSelectedMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Split model into parts"), self.splitSelectedMeshes)

        self._message = Message(title=catalog.i18nc("@info:title", "Mesh Tools"))

    def _onFileLoaded(self, file_name):
        self._currently_loading_files.append(file_name)

    def _onFileCompleted(self, file_name):
        if file_name in self._currently_loading_files:
            self._currently_loading_files.remove(file_name)

    def _onSceneChanged(self, node):
        if not node or not node.getMeshData():
            return

        # only check meshes that have just been loaded
        if node.getMeshData().getFileName() not in self._currently_loading_files:
            return

        # the scene may change multiple times while loading a mesh,
        # but we want to check the mesh only once
        if node not in self._check_node_queue:
            self._check_node_queue.append(node)
            self._application.callLater(self.checkQueuedNodes)

    def checkQueuedNodes(self):
        for node in self._check_node_queue:
            tri_node = self._toTriMesh(node.getMeshData())
            if tri_node.is_watertight:
                continue

            file_name = node.getMeshData().getFileName()
            base_name = os.path.basename(file_name)

            if file_name in self._mesh_not_watertight_messages:
                self._mesh_not_watertight_messages[file_name].hide()

            message = Message(title=catalog.i18nc("@info:title", "Mesh Tools"))
            body = catalog.i18nc("@info:status", "Model %s is not watertight, and may not print properly.") % base_name

            # XRayView may not be available if the plugin has been disabled
            if "XRayView" in self._controller.getAllViews() and self._controller.getActiveView().getPluginId() != "XRayView":
                body += " " + catalog.i18nc("@info:status", "Check X-Ray View and repair the model before printing it.")
                message.addAction("X-Ray", catalog.i18nc("@action:button", "Show X-Ray View"), None, "")
                message.actionTriggered.connect(self._showXRayView)
            else:
                body += " " +catalog.i18nc("@info:status", "Repair the model before printing it.")

            message.setText(body)
            message.show()

            self._mesh_not_watertight_messages[file_name] = message

        self._check_node_queue = []

    def _showXRayView(self, message, action):
        self._controller.setActiveView("XRayView")
        message.hide()

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
            new_node.setName(name if i==0 else "%s %d" % (name, i))
            new_node.callDecoration("setActiveExtruder", extruder_id)
            new_node.addDecorator(BuildPlateDecorator(build_plate))
            new_node.addDecorator(SliceableObjectDecorator())

            op.addOperation(AddSceneNodeOperation(new_node, parent))
            op.addOperation(SetTransformMatrixOperation(new_node, transformation))

        op.push()

    def _toTriMesh(self, mesh_data: MeshData) -> trimesh.base.Trimesh:
        indices = mesh_data.getIndices()
        if indices is None:
            # some file formats (eg 3mf) don't supply indices, but have unique vertices per face
            indices = numpy.arange(mesh_data.getVertexCount()).reshape(-1, 3)

        return trimesh.base.Trimesh(vertices=mesh_data.getVertices(), faces=indices, vertex_normals=mesh_data.getNormals())

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
