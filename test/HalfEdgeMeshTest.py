#!/usr/bin/env python3
# 
import numpy as np
import matplotlib.pyplot as plt

from fealpy.mesh import PolygonMesh, HalfEdgeMesh
from fealpy.mesh import TriangleMesh


class HalfEdgeMeshTest:

    def __init__(self):
        pass

    def refine_poly_test(self, plot=True):
        node = np.array([
            (0.0, 0.0), (0.0, 1.0), (0.0, 2.0),
            (1.0, 0.0), (1.0, 1.0), (1.0, 2.0),
            (2.0, 0.0), (2.0, 1.0), (2.0, 2.0)], dtype=np.float)
        cell = np.array([0, 3, 4, 4, 1, 0,
            1, 4, 5, 2, 3, 6, 7, 4, 4, 7, 8, 5], dtype=np.int)
        cellLocation = np.array([0, 3, 6, 10, 14, 18], dtype=np.int)

        mesh = PolygonMesh(node, cell, cellLocation)
        mesh = HalfEdgeMesh.from_polygonmesh(mesh)

        NE = mesh.number_of_edges()
        NC = mesh.number_of_cells()
        
        if True:
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[2] = True
            mesh.refine(isMarkedCell, dflag=False)
        
        if True:
            NC = mesh.number_of_cells()
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[6] = True
            mesh.refine(isMarkedCell, dflag=False)
        
        if True:
            NC = mesh.number_of_cells()
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[3] = True
            mesh.refine(isMarkedCell, dflag=False)
            
        if True:
            NC = mesh.number_of_cells()
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[1] = True
            isMarkedCell[5] = True
            mesh.refine(isMarkedCell, dflag=False)
            
        if True:
            NC = mesh.number_of_cells()
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[1] = True
            isMarkedCell[12] = True
            mesh.refine(isMarkedCell, dflag=False)
            
        if True:
            NC = mesh.number_of_cells()
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[0] = True
            isMarkedCell[21] = True
            mesh.refine(isMarkedCell, dflag=False)
            
        print("halfedge level:\n")
        for i, val in enumerate(mesh.halfedgedata['level']):
            print(i, ':', val, mesh.ds.halfedge[i, 0:2])
            
        print("cell level:\n")
        for i, val in enumerate(mesh.celldata['level']):
            print(i, ':', val)

        if plot:
            NN = mesh.number_of_nodes()
            nindex = np.zeros(NN, dtype=np.int)
            halfedge = mesh.ds.halfedge
            nindex[halfedge[:, 0]] = mesh.get_data('halfedge', 'level')
            cindex = mesh.get_data('cell', 'level')

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_edge(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)
            plt.show()
        else:
            return mesh

    def coarsen_poly_test(self, mesh, plot=True):

        NC = mesh.number_of_cells()
        isMarkedCell = np.zeros(NC+1, dtype=np.bool)
        isMarkedCell[2:10] = True
        isMarkedCell[23:26] = True
        isMarkedCell[[28, 29]] = True
        mesh.coarsen(isMarkedCell)

        if True:
            NC = mesh.number_of_cells()
            isMarkedCell = np.zeros(NC+1, dtype=np.bool)
            isMarkedCell[15:19] = True
            isMarkedCell[9:13] = True
            isMarkedCell[[8, 14, 13]] = True
            mesh.coarsen(isMarkedCell)

        if plot:
            NN = mesh.number_of_nodes()
            nlevel = np.zeros(NN, dtype=np.int)
            halfedge = mesh.ds.halfedge
            for i, idx in enumerate(halfedge):
                print(i, ": " , idx)
            nlevel[halfedge[:, 0]] = mesh.get_data('halfedge', 'level')
            clevel = mesh.get_data('cell', 'level')

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_plot(axes)
            mesh.find_node(axes, showindex=True, multiindex=nlevel)
            mesh.find_cell(axes, showindex=True, multiindex=clevel)
            plt.show()

    def triangle_mesh_test(self, plot=False):

        node = np.array([
            (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)
        ])
        cell = np.array([
            (1, 2, 0), (3, 0, 2)
        ])

        tmesh = TriangleMesh(node, cell) 
        tmesh.uniform_refine(n=1)
        mesh = HalfEdgeMesh.from_mesh(tmesh)
        if plot:
            halfedge = mesh.ds.halfedge
            for i, idx in enumerate(halfedge):
                print(i, ": " , idx)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_halfedge_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)
            plt.show()

    def refine_tri_test(self, plot=True):
        node = np.array([
            (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)
        ])
        cell = np.array([
            (1, 2, 0), (3, 0, 2)
        ])
        tmesh = TriangleMesh(node, cell) 
        tmesh.uniform_refine(n=1)
        mesh = HalfEdgeMesh.from_mesh(tmesh)
        if plot:
            halfedge = mesh.ds.halfedge
            for i, idx in enumerate(halfedge):
                print(i, ": " , idx)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_halfedge_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)
            plt.show()


    def voronoi_test(self, plot=False):
        from scipy.spatial import Delaunay
        from scipy.spatial import Voronoi, voronoi_plot_2d
        from scipy.spatial import KDTree
        
        points = np.random.rand(10, 2)
        print(points)

        # 边界点固定标记, 在网格生成与自适应算法中不能移除
        # 1: 固定
        # 0: 自由
        fflag = np.ones(4, dtype=np.bool)

        #  dflag 单元所处的子区域的标记编号
        #  0: 表示外部无界区域
        # -n: n >= 1, 表示编号为 -n 洞
        #  n: n >= 1, 表示编号为  n 的内部子区域
        dflag = np.array([1, 0])

        node = np.array([
            (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], dtype=np.float)
        halfedge = np.array([
            (1, 0, 1, 3, 4, 1),
            (2, 0, 2, 0, 5, 1),
            (3, 0, 3, 1, 6, 1),
            (0, 0, 0, 2, 7, 1),
            (0, 1, 7, 5, 0, 0),
            (1, 1, 4, 6, 1, 0),
            (2, 1, 5, 7, 2, 0),
            (3, 1, 6, 4, 3, 0)], dtype=np.int)
        NC = 1
        mesh = HalfEdgeMesh(node, halfedge, NC)
        mesh.set_data('fflag', fflag, 'node')
        mesh.set_data('dflag', dflag, 'cell')

        v = Voronoi(points)
        tree = KDTree(points)

        print("points:\n", v.points)
        print('vertices:\n', v.vertices)
        print('ridge_points:\n', v.ridge_points)
        print('ridge_vertices:\n', v.ridge_vertices)
        print('regions:\n', v.regions)
        print('point_region:\n', v.point_region)

        d, nidx = tree.query(node)
        print(nidx)

        if plot:
            halfedge = mesh.ds.halfedge
            for i, idx in enumerate(halfedge):
                print(i, ": " , idx)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_plot(axes)
            # mesh.find_node(axes, showindex=True, multiindex=nidx)
            mesh.find_node(axes, node=points, color='r', showindex=True)
            mesh.find_node(axes, node=v.vertices, color='b', showindex=True)
            voronoi_plot_2d(v, axes)

            fig = plt.figure()
            axes = fig.gca()
            mesh.add_halfedge_plot(axes)
            mesh.find_node(axes, showindex=True)
            mesh.find_cell(axes, showindex=True)
            plt.show()





test = HalfEdgeMeshTest()
#test.boundary_edge_to_edge_test()
#test.from_polygonmesh_test()
#test.refine_test()
#test.edge_to_cell_test()
#test.cell_barycenter_test(plot=False)
#mesh = test.refine_poly_test(plot=False)
#test.coarsen_poly_test(mesh, plot=True)
#test.triangle_mesh_test(plot=True)
test.voronoi_test(plot=True)