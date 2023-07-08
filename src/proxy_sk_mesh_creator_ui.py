
import maya.cmds as cmds
import maya.OpenMaya as om
from maya import OpenMayaUI as omui

from shiboken2 import wrapInstance
from PySide2 import QtCore, QtWidgets, QtGui
import webbrowser
import numpy as np

# TODO:
#  - Improve UI layout.
#  - Make window open/close while maintaining data and position.
#  - Option to export fbx for rig? (not anims).
#  - Options to choose axis of scaling/aiming.
#  - Clean code (better separation on single functions and UI vs logic).
#  - Improve naming of proxy geo.
#  - Find a way to delete properly multiple children of a single joint.


def maya_main_window():
    """
    Return Maya main window as a QMainWindow class instance.
    """

    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)

class ProxyRigCreatorLib(object):

    def __init__(self):
        self.proxy_geo_grp = 'proxy_geo_grp'
        self.proxy_geos = []
        self.max_length = 0.1

    def create_proxy_rig(self, parent: str = None):
        """

        Args:
            parent:
        """

        if not parent:
            sel = cmds.ls(sl=True)
            if sel:
                parent = sel[-1]

        if parent:
            children = cmds.listRelatives(parent, c=True, type='joint')
            if children:
                for c in children:
                    geo = self.create_geo(parent, c)
                    ProxyRigCreatorLib.aim(geo, c)
                    # ProxyRigCreatorLib.scale(geo, parent)
                    self.create_proxy_rig(c)
                    self.proxy_geos.append(geo)

            else:
                parent_jnt = cmds.listRelatives(parent, p=True, type='joint')[0]
                parent_geo = f'geo_{parent_jnt}__PROXY__'
                geo = cmds.polyCube(n=f'geo_{parent}__PROXY__')[0]
                cmds.matchTransform(geo, parent, pos=True, rot=False, scale=False)
                cmds.matchTransform(geo, parent_geo, pos=False, rot=True, scale=False)
                self_parent = cmds.listRelatives(parent, parent=True, type='joint')[0]
                self_parent_geo = f'geo_{self_parent}__PROXY__'
                cmds.addAttr(geo, shortName='len', longName='length', defaultValue=cmds.getAttr(f'{self_parent_geo}.length'))
                cmds.addAttr(geo, shortName='rad', longName='radius', defaultValue=cmds.getAttr(f'{parent}.radius'))
                self.proxy_geos.append(geo)

        else:
            om.MGlobal.displayError("Proxy Rig Creator: Select a root joint to start the process.")

    def group_proxy_geo(self, base_scale_factor: str = 1.0, radius_scale_factor: bool = False,
                        length_scale_factor: bool = False, excluded_jnts: list = None):
        if excluded_jnts is None:
            excluded_jnts = []
        self.proxy_geo_grp = cmds.group(n=self.proxy_geo_grp, em=True, w=True)
        for gp in self.proxy_geos:
            if cmds.objExists(gp):
                gp_jnt = gp.replace('geo_', '').split('__PROXY__')[0]
                print(gp)
                if gp_jnt in excluded_jnts:
                    cmds.delete(gp)
                else:
                    cmds.parent(gp, self.proxy_geo_grp)
                    scale_factor = base_scale_factor
                    if radius_scale_factor:
                        scale_factor *= cmds.getAttr(f'{gp}.radius')
                    if length_scale_factor:
                        scale_factor *= cmds.getAttr(f'{gp}.length')

                    cmds.setAttr(f'{gp}.sx', scale_factor)
                    cmds.setAttr(f'{gp}.sz', scale_factor)

        cmds.select(cl=True)

    def delete_proxy_geo(self):
        if cmds.objExists(self.proxy_geo_grp):
            cmds.delete(self.proxy_geo_grp)

    @staticmethod
    def get_color():
        print('hello')
        return QtWidgets.QColorDialog.getColor()

    @staticmethod
    def apply_color_to_geo():

        meshes = cmds.ls(sl=True)
        mat_name = 'test'
        color = QtWidgets.QColorDialog.getColor()

        for m in meshes:
            if cmds.objExists(m):

                shading_engine = cmds.shadingNode('lambert', name=mat_name, asShader=True)
                mat = cmds.sets(name=f'{mat_name}SG', empty=True, renderable=True, noSurfaceShader=True)
                cmds.connectAttr(f'{shading_engine}.outColor', f'{mat}.surfaceShader')

                cmds.setAttr(shading_engine + ".color", color.red() / 255, color.green() / 255, color.blue() / 255, type="double3")
                cmds.sets(meshes, forceElement=mat)

    def skin(self):
        proxy_geos = cmds.listRelatives(self.proxy_geo_grp, c=True)
        for pg in proxy_geos:
            jnt = pg.replace('geo_', '').split('__PROXY__')[0]
            cmds.select(jnt, r=True)
            cmds.skinCluster(jnt, pg, tsb=True, name='spine_skinCluster', bindMethod=0, skinMethod=0, normalizeWeights=1)[0]

    def parent_constrain(self):
        proxy_geos = cmds.listRelatives(self.proxy_geo_grp, c=True)
        for pg in proxy_geos:
            jnt = pg.replace('geo_', '').split('__PROXY__')[0]
            cmds.parentConstraint(jnt, pg, mo=True)

    @staticmethod
    def aim(src: str, dst: str):
        # use this only if a joint has multiple children

        base_wm = cmds.getAttr(src + '.wm')
        base_vec = [base_wm[12], base_wm[13], base_wm[14]]

        aim_wm = cmds.getAttr(dst + '.wm')
        aim_vec = [aim_wm[12], aim_wm[13], aim_wm[14]]

        up_base_vec = [aim_wm[8], aim_wm[9], aim_wm[10]]

        new_aim_vec = np.array(aim_vec) - np.array(base_vec)
        new_aim_vec = new_aim_vec / np.linalg.norm(new_aim_vec)

        side_vec = np.cross(up_base_vec, new_aim_vec)
        side_vec = side_vec / np.linalg.norm(side_vec)

        new_up_vec = np.cross(new_aim_vec, side_vec)
        new_up_vec = new_up_vec / np.linalg.norm(new_up_vec)

        scale = cmds.getAttr(f'{src}.scale')[0]

        orient_f16 = [new_up_vec[0], new_up_vec[1], new_up_vec[2], 0,
                      new_aim_vec[0], new_aim_vec[1], new_aim_vec[2], 0,
                      side_vec[0], side_vec[1], side_vec[2], 0,
                      base_vec[0], base_vec[1], base_vec[2], 1]

        cmds.xform(src, m=orient_f16, ws=True)
        cmds.setAttr(f'{src}.scale', scale[0], scale[1], scale[2])

    def create_geo(self, src_jnt: str, dst_jnt: str):

        cube = cmds.polyCube(n=f'geo_{src_jnt}__PROXY__')
        cmds.matchTransform(cube[0], src_jnt, pos=True, rot=False, scale=False)

        length = 1

        if dst_jnt:

            wm_src_jnt_f16 = cmds.xform(src_jnt, query=True, matrix=True, ws=True)
            wm_dst_jnt_f16 = cmds.xform(dst_jnt, query=True, matrix=True, ws=True)

            wm_src_jnt = om.MMatrix()
            wm_dst_jnt = om.MMatrix()

            om.MScriptUtil.createMatrixFromList(wm_src_jnt_f16, wm_src_jnt)
            om.MScriptUtil.createMatrixFromList(wm_dst_jnt_f16, wm_dst_jnt)

            wt_src_jnt = np.array([wm_src_jnt(3, 0), wm_src_jnt(3, 1), wm_src_jnt(3, 2)])
            wt_dst_jnt = np.array([wm_dst_jnt(3, 0), wm_dst_jnt(3, 1), wm_dst_jnt(3, 2)])
            aim_vec = wt_dst_jnt - wt_src_jnt
            length = np.linalg.norm(aim_vec)

            if length < 0.1:
                length = 0.1

        if length > self.max_length:
            self.max_length = length

        cmds.setAttr(f'{cube[1]}.height', length)
        cmds.move(0, length / 2, 0, f'{cube[0]}.vtx[0:7]', r=True, os=True, wd=True)

        cmds.addAttr(cube[0], shortName='len', longName='length', defaultValue=length / self.max_length)
        cmds.addAttr(cube[0], shortName='rad', longName='radius', defaultValue=cmds.getAttr(f'{src_jnt}.radius'))

        return cube[0]

    @staticmethod
    def get_root_jnt():
        sel = cmds.ls(sl=True) or ''

        if sel:
            sel = sel[-1]

        return sel

    @staticmethod
    def get_excluded_jnts():
        sel = cmds.ls(sl=True)
        excluded_jnts = []
        excluded_jnts_txt = ''

        if sel:
            for s in sel:
                excluded_jnts.append(s)
                excluded_jnts_txt += f'{s}, '

        return excluded_jnts, excluded_jnts_txt[:-2]


class ProxyRigCreatorUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super().__init__(parent=parent)

        self.proxy_rig_lib = ProxyRigCreatorLib()
        self.geo_color = None
        self.excluded_jnts_lst = []

        pos = QtGui.QCursor().pos()
        self.setGeometry(pos.x(), pos.y(), 400, 400)
        self.setWindowTitle("Proxy Rig Creator")
        #self.setWindowIcon(QtGui.QIcon(project.paths.shelf_icon("mesh_exporter")))
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMinimizeButtonHint)

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):

        self.creation_grp = QtWidgets.QGroupBox("Creation")
        self.root_jnt_btn = QtWidgets.QPushButton("Root Joint >>")
        self.sel_root_jnt = QtWidgets.QLineEdit("")
        self.exclude_jnts_btn = QtWidgets.QPushButton("Exclude Joints >>")
        self.sel_excluded_jnts = QtWidgets.QLineEdit("")
        self.size_grp = QtWidgets.QGroupBox("Size")
        self.base_scale_label = QtWidgets.QLabel("Base Scale")
        self.radius_scale_factor = QtWidgets.QCheckBox('Radius Scale Factor')
        self.length_scale_factor = QtWidgets.QCheckBox('Length Scale Factor')
        self.custom_scale_factor = QtWidgets.QDoubleSpinBox(minimum=0.0, value=1.0)

        self.create_btn = QtWidgets.QPushButton("Create")
        self.assign_color_btn =QtWidgets.QPushButton("Assign Color")


        self.binding_grp = QtWidgets.QGroupBox("Binding")
        self.parent_constrain_btn = QtWidgets.QPushButton("Parent Constrain")
        self.skin_btn = QtWidgets.QPushButton("Skin")

        self.delete_btn = QtWidgets.QPushButton("Delete Proxy Geo")
        self.close_btn = QtWidgets.QPushButton("Close")

    def create_layouts(self):
        # Layout creation
        main_layout = QtWidgets.QVBoxLayout(self)

        # Create menu bar
        menu_bar = QtWidgets.QMenuBar()
        main_layout.addWidget(menu_bar)

        help_bar_action = menu_bar.addMenu("Help")
        # help_bar_action.addAction("Tool Documentation", partial(webbrowser.open_new, self.url_doc))

        main_layout.addWidget(self.creation_grp, QtCore.Qt.AlignLeft)
        creation_grp_layout = QtWidgets.QVBoxLayout(self)
        self.creation_grp.setLayout(creation_grp_layout)

        root_jnt_layout = QtWidgets.QFormLayout(self)

        creation_grp_layout.addLayout(root_jnt_layout)

        root_jnt_layout.addRow(self.root_jnt_btn, self.sel_root_jnt)
        root_jnt_layout.addRow(self.exclude_jnts_btn, self.sel_excluded_jnts)
        root_jnt_layout.addRow(self.base_scale_label, self.custom_scale_factor)
        root_jnt_layout.addRow(self.length_scale_factor, self.radius_scale_factor)

        creation_grp_layout.addWidget(self.assign_color_btn)
        creation_grp_layout.addWidget(self.create_btn)

        main_layout.addWidget(self.binding_grp)
        binding_grp_layout = QtWidgets.QVBoxLayout(self)
        self.binding_grp.setLayout(binding_grp_layout)
        binding_grp_layout.addWidget(self.parent_constrain_btn)
        binding_grp_layout.addWidget(self.skin_btn)

        main_layout.addWidget(self.binding_grp)
        main_layout.addWidget(self.delete_btn)
        main_layout.addWidget(self.close_btn)

    def create_connections(self):
        self.assign_color_btn.clicked.connect(ProxyRigCreatorLib.apply_color_to_geo)
        self.root_jnt_btn.clicked.connect(lambda: self.sel_root_jnt.setText(ProxyRigCreatorLib.get_root_jnt()))
        self.exclude_jnts_btn.clicked.connect(self.set_excluded_jnts)
        self.create_btn.clicked.connect(lambda: self.proxy_rig_lib.create_proxy_rig(self.sel_root_jnt.text()))
        self.create_btn.clicked.connect(lambda: self.proxy_rig_lib.group_proxy_geo(self.custom_scale_factor.value(),
                                                                                   self.radius_scale_factor.isChecked(),
                                                                                   self.length_scale_factor.isChecked(),
                                                                                   self.excluded_jnts_lst))

        self.parent_constrain_btn.clicked.connect(self.proxy_rig_lib.parent_constrain)
        self.skin_btn.clicked.connect(self.proxy_rig_lib.skin)

        self.delete_btn.clicked.connect(self.proxy_rig_lib.delete_proxy_geo)
        self.close_btn.clicked.connect(self.close)

    def set_excluded_jnts(self):
        excluded_jnts_info = ProxyRigCreatorLib.get_excluded_jnts()

        self.excluded_jnts_lst = excluded_jnts_info[0]
        print(self.excluded_jnts_lst)
        self.sel_excluded_jnts.setText(excluded_jnts_info[1])

    def closeEvent(self, *args, **kwargs):
        self.deleteLater()


def show():
    proxy_rig_creator_ui = ProxyRigCreatorUI()
    proxy_rig_creator_ui.show()

    print(proxy_rig_creator_ui.custom_scale_factor.value())

    return proxy_rig_creator_ui
