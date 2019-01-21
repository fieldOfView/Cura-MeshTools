# Copyright (c) 2018 fieldOfView
# MeshTools is released under the terms of the AGPLv3 or higher.

from PyQt5.QtCore import QObject

import os.path
import numpy
import trimesh

from UM.Extension import Extension
from UM.Application import Application
from UM.Message import Message
from UM.Version import Version

from UM.Scene.Selection import Selection
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from UM.Mesh.MeshData import MeshData, calculateNormalsFromIndexedVertices
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Math.AxisAlignedBox import AxisAlignedBox

from cura.Scene.CuraSceneNode import CuraSceneNode

from .SetTransformMatrixOperation import SetTransformMatrixOperation
from .SetParentOperationSimplified import SetParentOperationSimplified

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

        self.addMenuItem(catalog.i18nc("@item:inmenu", "Check models"), self.checkMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix simple holes"), self.fixSimpleHolesForMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix model normals"), self.fixNormalsForMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Split model into parts"), self.splitMeshes)

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
        # in Cura 4, X-Ray view is in the preview stage
        version = Application.getInstance().getVersion()
        if version == "master" or Version(version) >= Version(4):
            self._controller.setActiveStage("PreviewStage")

        self._controller.setActiveView("XRayView")
        message.hide()

    def getSelectedNodes(self):
        self._message.hide()
        selection = Selection.getAllSelectedObjects()[:]
        if selection:
            return selection
        else:
            self._message.setText(catalog.i18nc("@info:status", "Please select one or more models first"))
            self._message.show()

    def checkMeshes(self):
        nodes_list = self.getSelectedNodes()
        if not nodes_list:
            return

        message_body = catalog.i18nc("@info:status", "Check summary:")
        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            message_body = message_body + "\n - %s" % node.getName()
            if tri_node.is_watertight:
                message_body = message_body + " " + catalog.i18nc("@info:status", "is watertight")
            else:
                message_body = message_body + " " + catalog.i18nc("@info:status", "is not watertight and may not print properly")
            if tri_node.body_count > 1:
                message_body = message_body + " " + catalog.i18nc("@info:status", "and consists of {body_count} submeshes").format(body_count = tri_node.body_count)

        self._message.setText(message_body)
        self._message.show()

    def fixSimpleHolesForMeshes(self):
        nodes_list = self.getSelectedNodes()
        if not nodes_list:
            return

        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            success = tri_node.fill_holes()
            self._replaceSceneNode(node, [tri_node])
            if not success:
                self._message.setText(catalog.i18nc("@info:status", "The mesh needs more extensive repair to become watertight"))
                self._message.show()

    def fixNormalsForMeshes(self):
        nodes_list = self.getSelectedNodes()
        if not nodes_list:
            return

        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            tri_node.fix_normals()
            self._replaceSceneNode(node, [tri_node])

    def splitMeshes(self):
        nodes_list = self.getSelectedNodes()
        if not nodes_list:
            return

        message_body = catalog.i18nc("@info:status", "Split result:")
        for node in nodes_list:
            message_body = message_body + "\n - %s" % node.getName()
            tri_node = self._toTriMesh(node.getMeshData())
            if tri_node.body_count > 1:
                self._replaceSceneNode(node, tri_node.split(only_watertight=False))
                message_body = message_body + " " + catalog.i18nc("@info:status", "was split in %d submeshes") % tri_node.body_count
            else:
                message_body = message_body + " " + catalog.i18nc("@info:status", "could not be split into submeshes")

        self._message.setText(message_body)
        self._message.show()

    def _replaceSceneNode(self, existing_node, trimeshes):
        name = existing_node.getName()
        file_name = existing_node.getMeshData().getFileName()
        transformation = existing_node.getWorldTransformation()
        parent = existing_node.getParent()
        extruder_id = existing_node.callDecoration("getActiveExtruder")
        build_plate = existing_node.callDecoration("getBuildPlateNumber")
        selected = Selection.isSelected(existing_node)

        children = existing_node.getChildren()
        new_nodes = []

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

            new_nodes.append(new_node)

            if selected:
                Selection.add(new_node)

        for child in children:
            child_bounding_box = child.getMeshData().getTransformed(child.getWorldTransformation()).getExtents()
            new_parent = None
            for potential_parent in new_nodes:
                parent_bounding_box = potential_parent.getMeshData().getTransformed(potential_parent.getWorldTransformation()).getExtents()
                if child_bounding_box.intersectsBox(parent_bounding_box) != AxisAlignedBox.IntersectionResult.NoIntersection:
                    new_parent = potential_parent
                    break
            if not new_parent:
                new_parent = new_nodes[0]
            op.addOperation(SetParentOperationSimplified(child, new_parent))

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
        for tri_face in tri_faces:
            face = []
            for tri_index in tri_face:
                vertices.append(tri_vertices[tri_index])
                face.append(index_count)
                index_count += 1
            indices.append(face)
            face_count += 1

        vertices = numpy.asarray(vertices, dtype=numpy.float32)
        indices = numpy.asarray(indices, dtype=numpy.int32)
        normals = calculateNormalsFromIndexedVertices(vertices, indices, face_count)

        mesh_data = MeshData(vertices=vertices, indices=indices, normals=normals)
        return mesh_data
