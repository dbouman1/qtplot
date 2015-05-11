import ConfigParser
import math
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import sys
import time

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.ticker import ScalarFormatter
from PyQt4 import QtGui, QtCore
from scipy.interpolate import griddata
from scipy.spatial import qhull, delaunay_plot_2d

from data import DatFile, Data
from linecut import Linecut, FixedOrderFormatter
from operations import Operations
from settings import Settings

class Window(QtGui.QMainWindow):
    """The main window of the qtplot application."""
    def __init__(self, lc_window, op_window, filename=None):
        QtGui.QMainWindow.__init__(self)

        self.filename = None
        
        self.linecut = lc_window
        self.operations = op_window
        self.settings = Settings()

        self.fig, self.ax = plt.subplots()
        self.cb = None

        self.line = None
        self.line_type = None
        self.line_coord = None
        self.line_start = None
        self.line_end = None
        self.line_calculate = False

        self.cmap_change = False

        self.dat_file = None
        self.data = None
        self.pcolor_data = None

        self.init_ui()

        if filename is not None:
            self.load_file(filename)
            #self.update_ui()

    def init_ui(self):
        self.setWindowTitle('qtplot')

        self.main_widget = QtGui.QWidget(self)

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_motion)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        # Top row buttons
        hbox = QtGui.QHBoxLayout()
        
        self.b_load = QtGui.QPushButton('Load DAT...')
        self.b_load.clicked.connect(self.on_load_dat)
        hbox.addWidget(self.b_load)

        self.b_refresh = QtGui.QPushButton('Refresh')
        self.b_refresh.clicked.connect(self.on_refresh)
        hbox.addWidget(self.b_refresh)

        self.b_swap_axes = QtGui.QPushButton('Swap axes', self)
        self.b_swap_axes.clicked.connect(self.on_swap_axes)
        hbox.addWidget(self.b_swap_axes)

        self.b_swap = QtGui.QPushButton('Swap order', self)
        self.b_swap.clicked.connect(self.on_swap_order)
        hbox.addWidget(self.b_swap)

        self.b_linecut = QtGui.QPushButton('Linecut')
        self.b_linecut.clicked.connect(self.linecut.show_window)
        hbox.addWidget(self.b_linecut)

        self.b_operations = QtGui.QPushButton('Operations')
        self.b_operations.clicked.connect(self.operations.show_window)
        hbox.addWidget(self.b_operations)

        # Subtracting series R
        r_hbox = QtGui.QHBoxLayout()

        lbl_sub = QtGui.QLabel('Sub series R:')
        r_hbox.addWidget(lbl_sub)

        lbl_v = QtGui.QLabel('V:')
        lbl_v.setMaximumWidth(20)
        r_hbox.addWidget(lbl_v)

        self.cb_v = QtGui.QComboBox(self)
        r_hbox.addWidget(self.cb_v)

        lbl_i = QtGui.QLabel('I:')
        lbl_i.setMaximumWidth(20)
        r_hbox.addWidget(lbl_i)

        self.cb_i = QtGui.QComboBox(self)
        r_hbox.addWidget(self.cb_i)

        lbl_r = QtGui.QLabel('R:')
        lbl_r.setMaximumWidth(20)
        r_hbox.addWidget(lbl_r)

        self.le_r = QtGui.QLineEdit(self)
        self.le_r.setMaximumWidth(100)
        r_hbox.addWidget(self.le_r)

        self.b_ok = QtGui.QPushButton('Ok', self)
        self.b_ok.clicked.connect(self.on_sub_series_r)
        self.b_ok.setMaximumWidth(50)
        r_hbox.addWidget(self.b_ok)

        # Selecting columns and orders
        grid = QtGui.QGridLayout()

        lbl_x = QtGui.QLabel("X:", self)
        grid.addWidget(lbl_x, 1, 1)

        self.cb_x = QtGui.QComboBox(self)
        self.cb_x.activated.connect(self.on_data_change)
        grid.addWidget(self.cb_x, 1, 2)

        lbl_order_x = QtGui.QLabel('X Order: ', self)
        grid.addWidget(lbl_order_x, 1, 3)

        self.cb_order_x = QtGui.QComboBox(self)
        self.cb_order_x.activated.connect(self.on_data_change)
        grid.addWidget(self.cb_order_x, 1, 4)

        lbl_y = QtGui.QLabel("Y:", self)
        grid.addWidget(lbl_y, 2, 1)

        self.cb_y = QtGui.QComboBox(self)
        self.cb_y.activated.connect(self.on_data_change)
        grid.addWidget(self.cb_y, 2, 2)

        lbl_order_y = QtGui.QLabel('Y Order: ', self)
        grid.addWidget(lbl_order_y, 2, 3)

        self.cb_order_y = QtGui.QComboBox(self)
        self.cb_order_y.activated.connect(self.on_data_change)
        grid.addWidget(self.cb_order_y, 2, 4)

        lbl_d = QtGui.QLabel("Data:", self)
        grid.addWidget(lbl_d, 3, 1)

        self.cb_z = QtGui.QComboBox(self)
        self.cb_z.activated.connect(self.on_data_change)
        grid.addWidget(self.cb_z, 3, 2)

        self.cb_save_default = QtGui.QCheckBox('Save as default columns')
        grid.addWidget(self.cb_save_default, 3, 3)

        # Colormap
        hbox_gamma = QtGui.QHBoxLayout()
        
        self.cb_reset_cmap = QtGui.QCheckBox('Reset on plot')
        self.cb_reset_cmap.setCheckState(QtCore.Qt.Checked)
        hbox_gamma.addWidget(self.cb_reset_cmap)

        self.le_min = QtGui.QLineEdit(self)
        self.le_min.setMaximumWidth(100)
        self.le_min.returnPressed.connect(self.on_cmap_changed)
        hbox_gamma.addWidget(self.le_min)

        self.s_min = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.s_min.valueChanged.connect(self.on_min_changed)
        hbox_gamma.addWidget(self.s_min)

        self.s_gamma = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.s_gamma.setMinimum(-100)
        self.s_gamma.setMaximum(100)
        self.s_gamma.setValue(0)
        self.s_gamma.valueChanged.connect(self.on_cmap_changed)
        hbox_gamma.addWidget(self.s_gamma)

        self.s_max = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.s_max.setValue(self.s_max.maximum())
        self.s_max.valueChanged.connect(self.on_max_changed)
        hbox_gamma.addWidget(self.s_max)

        self.le_max = QtGui.QLineEdit(self)
        self.le_max.setMaximumWidth(100)
        self.le_max.returnPressed.connect(self.on_cmap_changed)
        hbox_gamma.addWidget(self.le_max)

        # Bottom row buttons
        hbox4 = QtGui.QHBoxLayout()

        self.b_copy_colorplot = QtGui.QPushButton('Copy figure to clipboard (Ctrl+C)', self)
        self.b_copy_colorplot.clicked.connect(self.on_copy_figure)
        hbox4.addWidget(self.b_copy_colorplot)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, self.on_copy_figure)

        self.b_save_matrix = QtGui.QPushButton('Save data...')
        self.b_save_matrix.clicked.connect(self.on_save_matrix)
        hbox4.addWidget(self.b_save_matrix)

        self.b_settings = QtGui.QPushButton('Settings')
        self.b_settings.clicked.connect(self.settings.show_window)
        hbox4.addWidget(self.b_settings)

        # Main vertical box
        vbox = QtGui.QVBoxLayout(self.main_widget)
        vbox.addWidget(self.toolbar)
        vbox.addWidget(self.canvas)
        vbox.addLayout(hbox)
        vbox.addLayout(r_hbox)
        vbox.addLayout(grid)
        vbox.addLayout(hbox_gamma)
        vbox.addLayout(hbox4)

        self.status_bar = QtGui.QStatusBar()
        self.setStatusBar(self.status_bar)

        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

        self.move(100, 100)

    def update_ui(self, reset=True):
        self.setWindowTitle(self.name)

        columns = self.dat_file.df.columns.values

        self.cb_v.clear()
        self.cb_v.addItems(columns)

        self.cb_i.clear()
        self.cb_i.addItems(columns)

        i = self.cb_x.currentIndex()
        self.cb_x.clear()
        self.cb_x.addItems(columns)
        self.cb_x.setCurrentIndex(i)

        i = self.cb_order_x.currentIndex()
        self.cb_order_x.clear()
        self.cb_order_x.addItems(columns)
        self.cb_order_x.setCurrentIndex(i)

        i = self.cb_y.currentIndex()
        self.cb_y.clear()
        self.cb_y.addItems(columns)
        self.cb_y.setCurrentIndex(i)

        i = self.cb_order_y.currentIndex()
        self.cb_order_y.clear()
        self.cb_order_y.addItems(columns)
        self.cb_order_y.setCurrentIndex(i)

        i = self.cb_z.currentIndex()
        self.cb_z.clear()
        self.cb_z.addItems(columns)
        self.cb_z.setCurrentIndex(i)

        if reset:
            config = ConfigParser.RawConfigParser()
            path = os.path.dirname(os.path.realpath(__file__))
            config.read(os.path.join(path, 'qtplot.config'))

            combo_boxes = [self.cb_x, self.cb_order_x, self.cb_y, self.cb_order_y, self.cb_z]
            names = ['X', 'X Order', 'Y', 'Y Order', 'Data']
            default_indices = [0, 0, 1, 1, 3]

            if config.has_section('Settings'):
                indices = [cb.findText(config.get('Settings', names[i])) for i,cb in enumerate(combo_boxes)]

                for i, index in enumerate(indices):
                    if index != -1:
                        combo_boxes[i].setCurrentIndex(index)
                    else:
                        combo_boxes[i].setCurrentIndex(default_indices[i])
            else:
                for i, index in enumerate(default_indices):
                    combo_boxes[i].setCurrentIndex(index)

    def load_file(self, filename):
        self.dat_file = DatFile(filename)
        self.settings.load_file(filename)

        if filename != self.filename:
            path, self.name = os.path.split(filename)
            self.filename = filename

            self.line = None
            self.line_type = None
            self.line_coord = None
            self.line_start = None
            self.line_end = None

            self.update_ui()

        self.data = None
        self.pcolor_data = None

        #self.on_data_change()
        self.plot_2d_data(initial_plot=True)

    def on_load_dat(self, event):
        filename = str(QtGui.QFileDialog.getOpenFileName(filter='*.dat'))

        if filename != "":
            self.load_file(filename)

    def on_refresh(self, event):
        if self.filename:
            self.load_file(self.filename)

    def on_swap_axes(self, event):
        x, y = self.cb_x.currentIndex(), self.cb_y.currentIndex()
        self.cb_x.setCurrentIndex(y)
        self.cb_y.setCurrentIndex(x)

        if len(self.ax.lines) > 0:
            self.ax.lines.pop(0)

        if self.line_type == 'horizontal':
            self.line_type = 'vertical'
        elif self.line_type == 'vertical':
            self.line_type = 'horizontal'

        self.on_swap_order(event)

    def on_swap_order(self, event):
        x, y = self.cb_order_x.currentIndex(), self.cb_order_y.currentIndex()
        self.cb_order_x.setCurrentIndex(y)
        self.cb_order_y.setCurrentIndex(x)

        self.on_data_change()

    def on_sub_series_r(self, event):
        if self.dat_file == None:
            return

        V, I = str(self.cb_v.currentText()), str(self.cb_i.currentText())
        R = float(self.le_r.text())

        self.dat_file.df['SUB SERIES R'] = self.dat_file.df[V] - self.dat_file.df[I] * R

        self.update_ui(reset=False)

    def on_min_changed(self, value):
        if self.data != None:
            min, max = np.nanmin(self.data.values), np.nanmax(self.data.values)
            new = min + ((max - min) / 100) * value
            self.le_min.setText('%.2e' % new)

            self.on_cmap_changed()

    def on_max_changed(self, value):
        if self.data != None:
            min, max = np.nanmin(self.data.values), np.nanmax(self.data.values)
            new = min + ((max - min) / 100) * value
            self.le_max.setText('%.2e' % new)

            self.on_cmap_changed()

    def on_cmap_changed(self):
        self.cmap_change = True
        self.plot_2d_data(data_change=False)

    def on_mouse_press(self, event):
        if not event.inaxes or self.dat_file == None:
            return

        if event.button == 1:
            self.line_coord = self.data.get_closest_y(event.ydata)
            self.line_type = 'horizontal'
        elif event.button == 2:
            self.line_coord = self.data.get_closest_x(event.xdata)
            self.line_type = 'vertical'
        elif event.button == 3:
            self.line_start = (event.xdata, event.ydata)
            self.line_end = (event.xdata, event.ydata)
            self.line_type = 'arbitrary'
            self.line_calculate = False

        self.plot_linecut()

    def on_mouse_motion(self, event):
        if not event.inaxes or self.dat_file == None or event.button == None:
            return

        if event.button == 1 or event.button == 2:
            self.on_mouse_press(event)
        elif event.button == 3:
            self.line_end = (event.xdata, event.ydata)
            self.plot_linecut()

    def on_mouse_release(self, event):
        if not event.inaxes or self.line_start == None:
            return

        if event.button == 3:
            self.line_end = (event.xdata, event.ydata)
            self.line_calculate = True
            self.plot_linecut()

    def on_data_change(self):
        if self.dat_file is not None:
            self.generate_data()
            self.plot_2d_data(initial_plot=False)
            self.plot_linecut()

    def on_copy_figure(self):
        path = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(path, 'test.png')
        self.fig.savefig(path)

        img = QtGui.QImage(path)
        QtGui.QApplication.clipboard().setImage(img)

    def on_save_matrix(self):
        path = os.path.dirname(os.path.realpath(__file__))
        filename = QtGui.QFileDialog.getSaveFileName(self, 'Save file', path, '.dat')

        if filename != '' and self.dat_file != None:
            mat = np.dstack((self.data.x_coords, self.data.y_coords, self.data.values))

            mat.dump(str(filename))

    def get_axis_names(self):
        x_name = str(self.cb_x.currentText())
        y_name = str(self.cb_y.currentText())
        data_name = str(self.cb_z.currentText())
        order_x = str(self.cb_order_x.currentText())
        order_y = str(self.cb_order_y.currentText())

        return x_name, y_name, data_name, order_x, order_y

    def generate_data(self):
        x_name, y_name, data_name, order_x, order_y = self.get_axis_names()

        self.data = self.dat_file.get_data(x_name, y_name, data_name, order_x, order_y)
        self.data = self.operations.apply_operations(self.data)
        self.pcolor_data = self.data.get_pcolor()

        pd.DataFrame(self.data.values).to_clipboard()

        if self.pcolor_data[2].mask.any():
            self.status_bar.showMessage("Warning: Data contains NaN values")
        else:
            self.status_bar.showMessage("")

    def plot_2d_data(self, initial_plot=False, data_change=True):
        if self.dat_file is None:
            return

        self.ax.clear()

        x_name, y_name, data_name, order_x, order_y = self.get_axis_names()

        if self.pcolor_data == None:
            self.generate_data()
        
        # Set the axis range to increase upwards or to the left, and reverse if necessary
        self.ax.set_xlim(sorted(self.ax.get_xlim()))
        self.ax.set_ylim(sorted(self.ax.get_ylim()))
        x_flip, y_flip = self.data.is_flipped()
        if x_flip:
            self.ax.invert_xaxis()
        if y_flip:
            self.ax.invert_yaxis()

        self.quadmesh = self.ax.pcolormesh(*self.pcolor_data, cmap='seismic')
        #if self.data.tri != None:
        #    print 'plotting delaunay'
        #    delaunay_plot_2d(self.data.tri, self.ax)

        reset_cmap = self.cb_reset_cmap.checkState() == QtCore.Qt.Checked
        
        if initial_plot:
            cm_min, cm_max = self.quadmesh.get_clim()
            self.le_min.setText('%.2e' % cm_min)
            self.s_min.setValue(self.s_min.minimum())

            self.le_max.setText('%.2e' % cm_max)
            self.s_max.setValue(self.s_max.maximum())

            self.s_gamma.setValue(0)
        elif data_change:
            if reset_cmap:
                cm_min, cm_max = self.quadmesh.get_clim()
                self.le_min.setText('%.2e' % cm_min)
                self.s_min.setValue(self.s_min.minimum())
            
                self.le_max.setText('%.2e' % cm_max)
                self.s_max.setValue(self.s_max.maximum())

                self.s_gamma.setValue(0)
            else:
                gamma = 10.0**(self.s_gamma.value()/100.0)
                self.quadmesh.get_cmap().set_gamma(gamma)

                self.quadmesh.set_clim(vmin=float(self.le_min.text()), vmax=float(self.le_max.text()))
        else:
            gamma = 10.0**(self.s_gamma.value()/100.0)
            self.quadmesh.get_cmap().set_gamma(gamma)

            self.quadmesh.set_clim(vmin=float(self.le_min.text()), vmax=float(self.le_max.text()))

        self.ax.axis('tight')

        # Create a colorbar, if there is already one draw it in the existing place
        if self.cb:
            self.cb.update_bruteforce(self.quadmesh)
        else:
            self.cb = self.fig.colorbar(self.quadmesh)

        self.cb.set_label(data_name)
        self.cb.formatter = FixedOrderFormatter(1)
        self.cb.update_ticks()

        # Set the various labels
        self.ax.set_title(self.name)
        self.ax.set_xlabel(x_name)
        self.ax.set_ylabel(y_name)
        self.ax.xaxis.set_major_formatter(FixedOrderFormatter())
        self.ax.yaxis.set_major_formatter(FixedOrderFormatter())
        self.ax.set_aspect('auto')

        self.fig.tight_layout()
        
        self.canvas.draw()

        self.background = self.canvas.copy_from_bbox(self.ax.bbox)

        self.cmap_change = False

    def plot_linecut(self):
        if self.dat_file == None or self.line_type == None:
            return

        x_name, y_name, data_name, order_x, order_y = self.get_axis_names()

        if len(self.ax.lines) == 0:
            self.line = self.ax.axvline(color='red')

        if self.line_type == 'horizontal':
            self.line.set_transform(self.ax.get_yaxis_transform())
            self.line.set_data([0, 1], [self.line_coord, self.line_coord])

            x, y = self.data.get_row_at(self.line_coord)
            self.linecut.plot_linecut(x, y, self.name, x_name, data_name)
        elif self.line_type == 'vertical':
            self.line.set_transform(self.ax.get_xaxis_transform())
            self.line.set_data([self.line_coord, self.line_coord], [0, 1])

            x, y = self.data.get_column_at(self.line_coord)
            self.linecut.plot_linecut(x, y, self.name, y_name, data_name)
        elif self.line_type == 'arbitrary':
            self.line.set_transform(self.ax.transData)
            self.line.set_data([self.line_start[0], self.line_end[0]], [self.line_start[1], self.line_end[1]])

            if self.line_calculate:
                x = np.linspace(self.line_start[0], self.line_end[0], 1000)
                y = np.linspace(self.line_start[1], self.line_end[1], 1000)
                xi = np.column_stack((x, y))
                data = self.data.interpolate(xi)

                x -= x[0]
                y -= y[0]
                positions = np.sqrt(x**2 + y**2)
                
                self.linecut.plot_linecut(positions, data, self.name, 'Distance', data_name)

        # Redraw both plots to update them
        self.canvas.restore_region(self.background)
        self.ax.draw_artist(self.line)
        self.canvas.blit(self.ax.bbox)

    def resizeEvent(self, event):
        if len(self.ax.lines) > 0:
            self.ax.lines.pop(0)

        self.cmap_change = True

        # Very slow, maybe search for faster way
        # http://stackoverflow.com/questions/13552345/how-to-disable-multiple-auto-redrawing-at-resizing-widgets-in-pyqt
        self.plot_2d_data(data_change=False)

    def closeEvent(self, event):
        self.linecut.close()
        self.operations.close()
        self.settings.close()

        if self.cb_save_default.checkState() == QtCore.Qt.Checked:
            config = ConfigParser.RawConfigParser()
            config.add_section('Settings')
            x_name, y_name, data_name, order_x, order_y = self.get_axis_names()
            config.set('Settings', 'X', x_name)
            config.set('Settings', 'X Order', order_x)
            config.set('Settings', 'Y', y_name)
            config.set('Settings', 'Y Order', order_y)
            config.set('Settings', 'Data', data_name)

            path = os.path.dirname(os.path.realpath(__file__))
            with open(os.path.join(path, 'qtplot.config'), 'wb') as config_file:
                config.write(config_file)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)

    linecut = Linecut()
    operations = Operations()
    
    if len(sys.argv) > 1:
        main = Window(linecut, operations, filename=sys.argv[1])
    else:
        main = Window(linecut, operations)

    linecut.main = main
    operations.main = main

    linecut.show()
    operations.show()
    main.show()
    
    sys.exit(app.exec_())