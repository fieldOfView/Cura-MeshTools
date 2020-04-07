# Copyright (c) 2018 fieldOfView
# MeshTools is released under the terms of the AGPLv3 or higher.

from PyQt5.QtCore import pyqtSlot, QObject
from PyQt5.QtWidgets import QFileDialog

from cura.CuraApplication import CuraApplication
from UM.Extension import Extension
from UM.PluginRegistry import PluginRegistry
from UM.Message import Message
from UM.Logger import Logger

from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from UM.Mesh.MeshData import MeshData, calculateNormalsFromIndexedVertices
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Math.AxisAlignedBox import AxisAlignedBox
from UM.Mesh.ReadMeshJob import ReadMeshJob

from .SetTransformMatrixOperation import SetTransformMatrixOperation
from .SetParentOperationSimplified import SetParentOperationSimplified
from .SetMeshDataAndNameOperation import SetMeshDataAndNameOperation

from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

import os
import sys
import numpy
import trimesh

from typing import Optional, List

class MeshTools(Extension, QObject,):
    def __init__(self, parent = None) -> None:
        QObject.__init__(self, parent)
        Extension.__init__(self)

        self._application = CuraApplication.getInstance()
        self._controller = self._application.getController()

        self._application.engineCreatedSignal.connect(self._onEngineCreated)
        self._application.fileLoaded.connect(self._onFileLoaded)
        self._application.fileCompleted.connect(self._onFileCompleted)
        self._controller.getScene().sceneChanged.connect(self._onSceneChanged)

        self._currently_loading_files = [] #type: List[str]
        self._node_queue = [] #type: List[SceneNode]
        self._mesh_not_watertight_messages = {} #type: Dict[str, Message]

        self._rename_dialog = None

        self.addMenuItem(catalog.i18nc("@item:inmenu", "Reload model"), self.reloadMesh)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Rename model..."), self.renameMesh)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Replace models..."), self.replaceMeshes)
        self.addMenuItem("", lambda: None)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Check models"), self.checkMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix simple holes"), self.fixSimpleHolesForMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Fix model normals"), self.fixNormalsForMeshes)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Split model into parts"), self.splitMeshes)

        self._message = Message(title=catalog.i18nc("@info:title", "Mesh Tools"))
        self._additional_menu = None  # type: Optional[QObject]

    def _onEngineCreated(self) -> None:
        # To add items to the ContextMenu, we need access to the QML engine
        # There is no way to access the context menu directly, so we have to search for it
        context_menu = None
        for child in self._application.getMainWindow().contentItem().children():
            try:
                test = child.findItemIndex # only ContextMenu has a findItemIndex function
                context_menu = child
                break
            except:
                pass

        if not context_menu:
            return

        Logger.log("d", "Inserting item in context menu")
        context_menu.insertSeparator(0)
        context_menu.insertMenu(0, catalog.i18nc("@info:title", "Mesh Tools"))

        qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MeshToolsMenu.qml")
        self._additional_menu = self._application.createQmlComponent(qml_path, {"manager": self})
        if not self._additional_menu:
            return
        # Move additional menu items into context menu
        # This is handled in QML, because PyQt does not handle QtQuick1 objects very well
        self._additional_menu.moveToContextMenu(context_menu, 0)

    def _onFileLoaded(self, file_name) -> None:
        self._currently_loading_files.append(file_name)

    def _onFileCompleted(self, file_name) -> None:
        if file_name in self._currently_loading_files:
            self._currently_loading_files.remove(file_name)

    def _onSceneChanged(self, node) -> None:
        if not node or not node.getMeshData():
            return

        # only check meshes that have just been loaded
        if node.getMeshData().getFileName() not in self._currently_loading_files:
            return

        # the scene may change multiple times while loading a mesh,
        # but we want to check the mesh only once
        if node not in self._node_queue:
            self._node_queue.append(node)
            self._application.callLater(self.checkQueuedNodes)

    def checkQueuedNodes(self) -> None:
        for node in self._node_queue:
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

        self._node_queue = []

    def _showXRayView(self, message, action) -> None:
        try:
            major_api_version = self._application.getAPIVersion().getMajor()
        except AttributeError:
            # UM.Application.getAPIVersion was added for API > 6 (Cura 4)
            # Since this plugin version is only compatible with Cura 3.5 and newer, it is safe to assume API 5
            major_api_version = 5

        if major_api_version >= 6 and "SidebarGUIPlugin" not in PluginRegistry.getInstance().getActivePlugins():
            # in Cura 4.x, X-Ray view is in the preview stage
            self._controller.setActiveStage("PreviewStage")
        else:
            # in Cura 3.x, and in 4.x with the Sidebar GUI Plugin, X-Ray view is in the prepare stage
            self._controller.setActiveStage("PrepareStage")

        self._controller.setActiveView("XRayView")
        message.hide()

    def _getAllSelectedNodes(self) -> List[SceneNode]:
        self._message.hide()
        selection = Selection.getAllSelectedObjects()[:]
        if selection:
            deep_selection = []  # type: List[SceneNode]
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() != None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        self._message.setText(catalog.i18nc("@info:status", "Please select one or more models first"))
        self._message.show()

        return []  # type: List[SceneNode]

    @pyqtSlot()
    def checkMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
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

    @pyqtSlot()
    def fixSimpleHolesForMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            success = tri_node.fill_holes()
            self._replaceSceneNode(node, [tri_node])
            if not success:
                self._message.setText(catalog.i18nc("@info:status", "The mesh needs more extensive repair to become watertight"))
                self._message.show()

    @pyqtSlot()
    def fixNormalsForMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            tri_node.fix_normals()
            self._replaceSceneNode(node, [tri_node])

    @pyqtSlot()
    def splitMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
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

    @pyqtSlot()
    def replaceMeshes(self) -> None:
        self._node_queue = self._getAllSelectedNodes()
        if not self._node_queue:
            return

        options = QFileDialog.Options()
        if sys.platform == "linux" and "KDE_FULL_SESSION" in os.environ:
            options |= QFileDialog.DontUseNativeDialog
        filter_types = ";;".join(self._application.getMeshFileHandler().supportedReadFileTypes)

        directory = None
        if self._node_queue[0].getMeshData() is not None:
            directory = self._node_queue[0].getMeshData().getFileName()
        if not directory:
            directory = self._application.getDefaultPath("dialog_load_path").toLocalFile()

        file_name, _ = QFileDialog.getOpenFileName(
            parent=None,
            caption=catalog.i18nc("@title:window", "Select Replacement Mesh File"),
            directory=directory, options=options, filter=filter_types
        )
        if not file_name:
            self._node_queue = [] #type: List[SceneNode]
            return

        job = ReadMeshJob(file_name)
        job.finished.connect(self._readMeshFinished)
        job.start()

    @pyqtSlot()
    def renameMesh(self) -> None:
        self._node_queue = self._getAllSelectedNodes()
        if not self._node_queue or len(self._node_queue) > 1:
            self._message.hide()
            self._message.setText(catalog.i18nc("@info:status", "Please select a single model"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RenameDialog.qml")
        self._rename_dialog = self._application.createQmlComponent(path, {"manager": self})
        self._rename_dialog.show()
        self._rename_dialog.setName(self._node_queue[0].getName())
        print(self._node_queue[0].getName())

    @pyqtSlot(str)
    def setSelectedMeshName(self, new_name:str) -> None:
        node = self._node_queue[0]
        node.setName(new_name)
        Selection.remove(node)
        Selection.add(node)

    @pyqtSlot()
    def reloadMesh(self) -> None:
        self._node_queue = self._getAllSelectedNodes()
        if not self._node_queue or len(self._node_queue) > 1:
            self._message.hide()
            self._message.setText(catalog.i18nc("@info:status", "Please select a single model"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        mesh_data = self._node_queue[0].getMeshData()
        if not mesh_data:
            self._message.setText(catalog.i18nc("@info:status", "Reloading a group is not supported"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        file_name = mesh_data.getFileName()
        if not file_name:
            self._message.setText(catalog.i18nc("@info:status", "No link to the original file was found"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        job = ReadMeshJob(file_name)
        job.finished.connect(self._readMeshFinished)
        job.start()

    def _readMeshFinished(self, job) -> None:
        job_result = job.getResult()
        if len(job_result) == 0:
            self._message.setText(catalog.i18nc("@info:status", "Failed to load mesh"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        mesh_data = job_result[0].getMeshData()
        if not mesh_data:
            self._message.setText(catalog.i18nc("@info:status", "File contained no mesh data"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        mesh_name = os.path.basename(mesh_data.getFileName())

        has_merged_nodes = False

        op = GroupedOperation()
        for node in self._node_queue:
            op.addOperation(SetMeshDataAndNameOperation(node, mesh_data, mesh_name))

            if not isinstance(node, CuraSceneNode) or not node.getMeshData():
                if node.getName() == "MergedMesh":
                    has_merged_nodes = True
        op.push()

        if has_merged_nodes:
            self._application.updateOriginOfMergedMeshes()

        self._node_queue = [] #type: List[SceneNode]

    def _replaceSceneNode(self, existing_node, trimeshes) -> None:
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
            mesh_data = self._toMeshData(tri_node, file_name)

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

    def _toMeshData(self, tri_node: trimesh.base.Trimesh, file_name: str = "") -> MeshData:
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

        mesh_data = MeshData(file_name = file_name, vertices=vertices, indices=indices, normals=normals)
        return mesh_data
