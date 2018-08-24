# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# MeshTools is released under the terms of the AGPLv3 or higher.

from . import MeshTools

def getMetaData():
    return {}

def register(app):
    return {"extension": MeshTools.MeshTools()}
