import numpy as np
from scipy.sparse import coo_matrix, csc_matrix, csr_matrix, spdiags, eye, tril, triu
from ..quadrature import TriangleQuadrature
from .Mesh2d import Mesh2d
from .adaptive_tools import mark
from .mesh_tools import show_halfedge_mesh

# fixednode: 节点是否固定标记, 在网格生成与自适应算法中不能移除
# True: 固定
# False: 自由

# subdomain: 单元所处的子区域的标记编号
#  0: 表示外部无界区域
# -n: n >= 1, 表示编号为 -n 洞
#  n: n >= 1, 表示编号为  n 的内部子区域

class HalfEdgeMesh(Mesh2d):
    def __init__(self, node, halfedge, 
        NC=None,  fixednode=None, subdomain=None,
        nodelevel=None, celllevel=None, halfedgelevel=None):
        """
        Parameters
        ----------
        node : (NN, GD)
        halfedge : (2*NE, 6), 
            halfedge[i, 0]: the index of the vertex the i-th halfedge point to
            halfedge[i, 1]: the index of the cell the i-th halfedge blong to
            halfedge[i, 2]: the index of the next halfedge of th i-th halfedge 
            halfedge[i, 3]: the index of the previous halfedge of the i-th halfedge
            halfedge[i, 4]: the index of the opposit halfedge of the i-th halfedge
            halfedge[i, 5]: the main halfedge flag, 1: main halfedge; 0: non main halfedge
        """
        self.node = node
        self.ds = HalfEdgeMesh2dDataStructure(node.shape[0], NC, halfedge)
        self.meshtype = 'halfedge'
        self.itype = halfedge.dtype
        self.ftype = node.dtype

        self.halfedgedata = {}
        self.celldata = {}
        self.nodedata = {}
        self.edgedata = {}
        self.facedata = self.edgedata
        self.meshdata = {}

        self.init_level_info()

        if subdomain is not None:
            self.celldata['subdomain'] = subdomain

        if fixednode is not None:
            self.nodedata['fixednode'] = fixednode

        if nodelevel is not None:
            self.nodedata['level'] = nodelevel

        if celllevel is not None:
            self.celldata['level'] = celllevel

        if halfedgelevel is not None:
            self.halfedgedata['level'] = halfedgelevel


    def init_level_info(self):
        NN = self.number_of_nodes()
        NE = self.number_of_edges()
        NC = self.number_of_cells()

        self.celldata['level'] = np.zeros(NC+1, dtype=self.itype)
        self.halfedgedata['level'] = np.zeros(2*NE, dtype=self.itype)
        self.nodedata['level'] = np.zeros(NN, dtype=self.itype)

    def set_data(self, name, val, etype):
        if etype in {'cell', 2}:
            self.celldata[name] = val
        elif etype in {'face', 'edge', 1}:
            self.edgedata[name] = val
        elif etype in {'node', 0}:
            self.nodedata[name] = val
        elif etype == 'mesh':
            self.meshdata[name] = val
        elif etype == 'halfedge':
            self.halfedgedata[name] = val
        else:
            raise ValueError("`etype` is wrong!")

    def get_data(self, etype, name):
        if etype in {'cell', 2}:
            NC = self.number_of_cells()
            return self.celldata[name][0:NC]
        elif etype in {'face', 'edge', 1}:
            return self.edgedata[name]
        elif etype in {'node', 0}:
            return self.nodedata[name]
        elif etype == 'mesh':
            return self.meshdata[name]
        elif etype == 'halfedge':
            return self.halfedgedata[name]
        else:
            raise ValueError("`etype` is wrong!")

    def integrator(self, k):
        return TriangleQuadrature(k)

    @classmethod
    def from_mesh(cls, mesh):
        NN = mesh.number_of_nodes()
        NE = mesh.number_of_edges()
        NC = mesh.number_of_cells()
        NV = mesh.number_of_vertices_of_cells()

        node = mesh.entity('node')
        edge = mesh.entity('edge')
        cell = mesh.entity('cell')
        cell2edge = mesh.ds.cell_to_edge()
        edge2cell = mesh.ds.edge_to_cell()
        isInEdge = edge2cell[:, 0] != edge2cell[:, 1]
        sign = mesh.ds.cell_to_edge_sign()
        cell2edgeSign = np.zeros((NC, NV), dtype=mesh.itype)
        cell2edgeSign[~sign] = NE
        nex, pre = mesh.ds.boundary_edge_to_edge()

        halfedge = np.zeros((2*NE, 6), dtype=mesh.itype)


        # 指向的顶点
        halfedge[:NE, 0] = edge[:, 1]
        halfedge[NE:, 0] = edge[:, 0]

        # 指向的单元
        halfedge[:NE, 1] = edge2cell[:, 0]
        halfedge[NE:, 1] = edge2cell[:, 1]
        halfedge[NE:, 1][~isInEdge] = NC

        # 下一条边
        idx = cell2edge[edge2cell[:, 0], (edge2cell[:, 2]+1)%NV]
        idx += cell2edgeSign[edge2cell[:, 0], (edge2cell[:, 2]+1)%NV]
        halfedge[:NE, 2] = idx

        idx = cell2edge[edge2cell[isInEdge, 1], (edge2cell[isInEdge, 3]+1)%NV]
        idx += cell2edgeSign[edge2cell[isInEdge, 1], (edge2cell[isInEdge, 3]+1)%NV]
        halfedge[NE:, 2][isInEdge] = idx
        halfedge[NE:, 2][~isInEdge] = NE + nex

        # 前一条边 
        halfedge[halfedge[:, 2], 3] = range(2*NE)

        # 对偶半边
        halfedge[:NE, 4] = range(NE, 2*NE)
        halfedge[NE:, 4] = range(NE)

        # 主半边
        halfedge[:NE, 5] = 1

        return cls(node, halfedge, NC)

    @classmethod
    def from_polygonmesh(cls, mesh):
        NC = mesh.number_of_cells()
        NN = mesh.number_of_nodes()
        NE = mesh.number_of_edges()
        NV = mesh.number_of_vertices_of_cells()

        node = mesh.entity('node')
        edge = mesh.entity('edge')
        cell, cellLocation = mesh.entity('cell')
        cell2edge = mesh.ds.cell_to_edge(sparse=False)
        edge2cell = mesh.ds.edge_to_cell()
        cell2edgeSign = mesh.ds.cell_to_edge_sign(sparse=False)
        cell2edgeSign[cell2edgeSign==1] = 0
        cell2edgeSign[cell2edgeSign==-1] = NE

        isInEdge = edge2cell[:, 0] != edge2cell[:, 1]

        nex, pre = mesh.ds.boundary_edge_to_edge()

        halfedge = np.zeros((2*NE, 6), dtype=mesh.itype)
        # 指向的顶点
        halfedge[:NE, 0] = edge[:, 1]
        halfedge[NE:, 0] = edge[:, 0]

        # 指向的单元
        halfedge[:NE, 1] = edge2cell[:, 0]
        halfedge[NE:, 1] = edge2cell[:, 1]
        halfedge[NE:, 1][~isInEdge] = NC

        # 在指向单元中的下一条边
        idx = cellLocation[edge2cell[:, 0]] + (edge2cell[:, 2] + 1)%NV[edge2cell[:,  0]]
        halfedge[:NE, 2] = cell2edge[idx] + cell2edgeSign[idx]

        idx = cellLocation[edge2cell[isInEdge, 1]] + (edge2cell[isInEdge, 3] + 1)%NV[edge2cell[isInEdge,  1]]
        halfedge[NE:, 2][isInEdge] = cell2edge[idx] + cell2edgeSign[idx]
        halfedge[NE:, 2][~isInEdge] = NE + nex

        # 在指向单元中的上一条边
        idx = cellLocation[edge2cell[:, 0]] + (edge2cell[:, 2] - 1)%NV[edge2cell[:,  0]]
        halfedge[:NE, 3] = cell2edge[idx] + cell2edgeSign[idx]

        idx = cellLocation[edge2cell[isInEdge, 1]] + (edge2cell[isInEdge, 3] - 1)%NV[edge2cell[isInEdge,  1]]
        halfedge[NE:, 3][isInEdge] = cell2edge[idx] + cell2edgeSign[idx]
        halfedge[NE:, 3][~isInEdge] = NE + pre

        # 相反的halfedge
        halfedge[:NE, 4] = range(NE, 2*NE)
        halfedge[NE:, 4] = range(NE)

        # 标记主半边 ：1：主半边， 0：对偶半边
        halfedge[:NE, 5] = 1
        return cls(node, halfedge, NC)

    def entity(self, etype=2):
        if etype in {'cell', 2}:
            return self.ds.cell_to_node(sparse=False)
        elif etype in {'edge', 'face', 1}:
            return self.ds.edge_to_node(sparse=False)
        elif etype in {'halfedge'}:
            return self.ds.halfedge
        elif etype in {'node', 0}:
            return self.node
        else:
            raise ValueError("`entitytype` is wrong!")

    def entity_barycenter(self, etype='cell', index=None):
        node = self.node
        dim = self.geo_dimension()
        if etype in {'cell', 2}:
            cell2node = self.ds.cell_to_node()
            NV = self.ds.number_of_vertices_of_cells().reshape(-1,1)
            bc = cell2node*node/NV
        elif etype in {'edge', 'face', 1}:
            edge = self.ds.edge_to_node(sparse=False)
            bc = np.sum(node[edge, :], axis=1).reshape(-1, dim)/edge.shape[1]
        elif etype in {'node', 1}:
            bc = node
        return bc

    def node_normal(self):
        node = self.node
        cell, cellLocation = self.entity('cell')

        idx1 = np.zeros(cell.shape[0], dtype=np.int)
        idx2 = np.zeros(cell.shape[0], dtype=np.int)

        idx1[0:-1] = cell[1:]
        idx1[cellLocation[1:]-1] = cell[cellLocation[:-1]]
        idx2[1:] = cell[0:-1]
        idx2[cellLocation[:-1]] = cell[cellLocation[1:]-1]

        w = np.array([(0,-1),(1,0)])
        d = node[idx1] - node[idx2]
        return 0.5*d@w

    def cell_area(self, index=None):
        NC = self.number_of_cells()
        node = self.entity('node')
        halfedge = self.ds.halfedge

        e0 = halfedge[halfedge[:, 3], 0]
        e1 = halfedge[:, 0]

        w = np.array([[0, -1], [1, 0]], dtype=np.int)
        v= (node[e1] - node[e0])@w
        val = np.sum(v*node[e0], axis=1)

        a = np.zeros(NC+1, dtype=self.ftype)
        np.add.at(a, halfedge[:, 1], val)
        a /=2
        return a[:-1]

    def cell_barycenter(self):
        GD = self.geo_dimension()
        NC = self.number_of_cells()
        node = self.entity('node')
        halfedge = self.ds.halfedge

        e0 = halfedge[halfedge[:, 3], 0]
        e1 = halfedge[:, 0]

        w = np.array([[0, -1], [1, 0]], dtype=np.int)
        v= (node[e1] - node[e0])@w
        val = np.sum(v*node[e0], axis=1)
        ec = val.reshape(-1, 1)*(node[e1]+node[e0])/2

        a = np.zeros(NC+1, dtype=self.ftype)
        c = np.zeros((NC+1, GD), dtype=self.ftype)
        np.add.at(a, halfedge[:, 1], val)
        np.add.at(c, (halfedge[:, 1], np.s_[:]), ec)
        a /=2
        c /=3*a.reshape(-1, 1)
        return c[:-1]

    def edge_bc_to_point(self, bcs, index=None):
        node = self.entity('node')
        edge = self.entity('edge')
        index = index if index is not None else np.s_[:]
        ps = np.einsum('ij, kjm->ikm', bcs, node[edge[index]])
        return ps

    def refine_tri(self, isMarkedCell):
        """
        这里假设所有的单元都是三角形, 标记的单元一分为 4
        如果有一个单元有两个边被标记, 则剩下的一个边也需要被标记
        """

        NN = self.number_of_nodes()
        NE = self.number_of_edges()
        NC = self.number_of_cells()
        
        # 单元和半边的层标记信息
        clevel = self.celldata['level']
        nlevel = self.nodedata['level']

        halfedge = self.ds.halfedge
        isMainHEdge = (halfedge[:, 5] == 1) # 主半边标记

        # 标记出二分的半边

        isBHEdge = (clevel[halfedge[:, 1]] == nlevel[halfedge[:, 0]])
        isBHEdge = isBHEdge & (nlevel[halfedge[:, 0]]  > nlevel[halfedge[halfedge[:, 2], 0]])
        isBHEdge = isBHEdge & (nlevel[halfedge[:, 0]]  > nlevel[halfedge[halfedge[:, 3], 0]])
        isBHEdge = isBHEdge & (nlevel[halfedge[:, 0]] == clevel[halfedge[halfedge[:, 4], 1]])

        """
        halfedge[halfedge[isBHEdge, 4], 1] = halfedge[isBHEdge, 1]
        nex = halfedge[halfedge[isBHEdge, 4], 2]
        pre = halfedge[halfedge[isBHEdge, 4], 3]
        halfedge[nex, 1] = halfedge[isBHEdge, 1]
        halfedge[pre, 1] = halfedge[isBHEdge, 1]
        halfedge[halfedge[isBHEdge, 2], 3] = pre
        halfedge[halfedge[isBHEdge, 3], 2] = nex
        """

        # 标记出需要加密的半边
        isMarkedHEdge = isMarkedCell[halfedge[:, 1]] & (~isBHEdge) 
        flag = ~isMarkedHEdge & isMarkedHEdge[halfedge[:, 4]]
        isMarkedHEdge[flag] = True

        N = isMarkedHEdge.sum()

        node = self.entity('node')
        flag0 = isMainHEdge & isMarkedHEdge
        idx = halfedge[flag0, 4]
        ec = (node[halfedge[flag0, 0]] + node[halfedge[idx, 0]])/2
        NE1 = len(ec)

    def coarsen_tri(self, isMarkedCell):
        pass

    def refine_quad(self, isMarkedCell):
        pass

    def coarsen_quad(self, isMarkedCell):
        pass
    
    def refine_poly(self, isMarkedCell, data=None, dflag=False):
        NN = self.number_of_nodes()
        NE = self.number_of_edges()
        NC = self.number_of_cells()
        
        bc = self.cell_barycenter()

        # 单元和半边的层标记信息
        clevel = self.celldata['level']
        hlevel = self.halfedgedata['level']

        halfedge = self.ds.halfedge
        isMainHEdge = (halfedge[:, 5] == 1) # 主半边标记

        # 标记边
        flag0 = (hlevel - clevel[halfedge[:, 1]]) <= 0
        flag1 = (hlevel[halfedge[:, 3]] - clevel[halfedge[:, 1]]) <= 0
        isMarkedHEdge = isMarkedCell[halfedge[:, 1]] & flag0 & flag1 
        flag = ~isMarkedHEdge & isMarkedHEdge[halfedge[:, 4]]
        isMarkedHEdge[flag] = True

        node = self.entity('node')
        flag0 = isMainHEdge & isMarkedHEdge
        idx = halfedge[flag0, 4]
        ec = (node[halfedge[flag0, 0]] + node[halfedge[idx, 0]])/2
        NE1 = len(ec)
        
        if data is not None:
            NV = self.ds.number_of_vertices_of_cells(returnall=True)
            for key, value in data.items():
                evalue = (value[halfedge[flag0, 0]] + value[halfedge[idx, 0]])/2
                cvalue = np.zeros(NC+1, dtype=self.ftype)
                np.add.at(cvalue, halfedge[:, 1], value[halfedge[:, 0]])
                cvalue /= NV
                data[key] = np.concatenate((value, evalue, cvalue[isMarkedCell]), axis=0)
        #细分边
        halfedge1 = np.zeros((2*NE1, 6), dtype=self.itype)
        flag1 = isMainHEdge[isMarkedHEdge] # 标记加密边中的主半边
        halfedge1[flag1, 0] = range(NN, NN+NE1) # 新的节点编号
        idx0 = np.argsort(idx) # 当前边的对偶边的从小到大进行排序
        halfedge1[~flag1, 0] = halfedge1[flag1, 0][idx0] # 按照排序

        hlevel1 = np.zeros(2*NE1, dtype=self.itype)
        hlevel1[flag1] = np.maximum(hlevel[flag0], hlevel[halfedge[flag0, 3]]) + 1
        hlevel1[~flag1] = np.maximum(hlevel[idx], hlevel[halfedge[idx, 3]])[idx0]+1

        halfedge1[:, 1] = halfedge[isMarkedHEdge, 1]
        halfedge1[:, 3] = halfedge[isMarkedHEdge, 3] # 前一个 
        halfedge1[:, 4] = halfedge[isMarkedHEdge, 4] # 对偶边
        halfedge1[:, 5] = halfedge[isMarkedHEdge, 5] # 主边标记

        halfedge[isMarkedHEdge, 3] = range(2*NE, 2*NE + 2*NE1)
        idx = halfedge[isMarkedHEdge, 4] # 原始对偶边
        halfedge[isMarkedHEdge, 4] = halfedge[idx, 3]  # 原始对偶边的前一条边是新的对偶边

        halfedge = np.r_['0', halfedge, halfedge1]
        halfedge[halfedge[:, 3], 2] = range(2*NE+2*NE1)
        hlevel = np.r_[hlevel, hlevel1]

        if dflag:
            self.halfedgedata['level'] = hlevel 
            self.node = np.r_['0', node, ec]
            self.ds.reinit(NN+NE1, NC, halfedge)
            return

        # 细分单元
        flag = (hlevel - clevel[halfedge[:, 1]]) == 1
        N = halfedge.shape[0]
        NV = np.zeros(NC+1, dtype=self.itype)
        np.add.at(NV, halfedge[:, 1], flag)
        NHE = sum(NV[isMarkedCell])
        halfedge1 = np.zeros((2*NHE, 6), dtype=self.itype)
        hlevel1 = np.zeros(2*NHE, dtype=self.itype)
        
        NC1 = isMarkedCell.sum() # 加密单元个数
        
        # 当前为标记单元的可以加密的半边
        flag0 = flag & isMarkedCell[halfedge[:, 1]]
        idx0, = np.nonzero(flag0)
        nex0 = halfedge[flag0, 2]
        pre0 = halfedge[flag0, 3]
        
        # 修改单元的编号
        halfedge[halfedge[:, 1] == NC, 1] = NC + NHE
        cellidx = halfedge[idx0, 1] #需要加密的单元编号
        halfedge[idx0, 1] = range(NC, NC + NHE)
        clevel[isMarkedCell] += 1
        clevel1 = clevel[cellidx] # 单元层数加一
        
        idx1 = idx0.copy()
        pre = halfedge[idx1, 3]
        flag0 = ~flag[pre] # 前一个是不需要细分的半边
        while np.any(flag0):
            idx1[flag0] = pre[flag0]
            pre = halfedge[idx1, 3]
            flag0 = ~flag[pre] 
            halfedge[idx1, 1] = halfedge[idx0, 1]
            
        nex1 = halfedge[idx1, 2] # 当前半边的下一个半边
        pre1 = halfedge[idx1, 3] # 当前半边的上一个半边

        cell2newNode = np.full(NC+1, NN+NE1, dtype=self.itype)
        cell2newNode[isMarkedCell] += range(isMarkedCell.sum()) 
        
        halfedge[idx0, 2] = range(N, N+NHE) # idx0 的下一个半边的编号
        halfedge[idx1, 3] = range(N+NHE, N+2*NHE) # idx1 的上一个半边的编号
        
        halfedge1[:NHE, 0] = cell2newNode[cellidx]
        halfedge1[:NHE, 1] = halfedge[idx0, 1]
        halfedge1[:NHE, 2] = halfedge[idx1, 3]
        halfedge1[:NHE, 3] = idx0
        halfedge1[:NHE, 4] = halfedge[nex0, 3]
        halfedge1[:NHE, 5] = 1
        hlevel1[:NHE] = clevel[cellidx]

        halfedge1[NHE:, 0] = halfedge[pre1, 0]
        halfedge1[NHE:, 1] = halfedge[idx1, 1]
        halfedge1[NHE:, 2] = idx1
        halfedge1[NHE:, 3] = halfedge[idx0, 2]
        halfedge1[NHE:, 4] = halfedge[pre1, 2]
        halfedge1[NHE:, 5] = 0
        hlevel1[NHE:] = clevel[cellidx]

        halfedge = np.r_['0', halfedge, halfedge1]

        clevel = np.r_[clevel[:-1], clevel1, np.array([0])]
        flag = np.zeros(NC+NHE+1, dtype=np.bool)
        np.add.at(flag, halfedge[:, 1], True)
        idxmap = np.zeros(NC+NHE+1, dtype=self.itype)
        NC = flag.sum()
        idxmap[flag] = range(NC)
        halfedge[:, 1] = idxmap[halfedge[:, 1]]
        clevel = clevel[flag]

        self.halfedgedata['level'] = np.r_[hlevel, hlevel1]
        self.celldata['level'] = clevel
        self.node = np.r_['0', node, ec, bc[isMarkedCell[:-1]]]
        self.ds.reinit(NN+NE1+NC1, NC-1, halfedge)
    
    def coarsen_poly(self, isMarkedCell, dflag=True):
        NN = self.number_of_nodes()
        NE = self.number_of_edges()
        NC = self.number_of_cells()
        
        hlevel = self.halfedgedata['level']
        clevel = self.celldata['level']

        halfedge = self.ds.halfedge
        # 可以移除的网格节点
        isRNode = np.ones(NN, dtype=np.bool) # Removable node flag array
        flag = (hlevel == clevel[halfedge[:, 1]])
        np.logical_and.at(isRNode, halfedge[:, 0], flag)
        flag = (hlevel == hlevel[halfedge[:, 4]])
        np.logical_and.at(isRNode, halfedge[:, 0], flag)
        flag = isMarkedCell[halfedge[:, 1]]
        np.logical_and.at(isRNode, halfedge[:, 0], flag)

        nn = isRNode.sum()
        if nn > 0:
            # 重新标记要移除的单元
            isMarkedCell = np.zeros(NC+nn+1, dtype=np.bool)
            isMarkedHEdge = isRNode[halfedge[:, 0]] | isRNode[halfedge[halfedge[:, 4], 0]]
            isMarkedCell[halfedge[isMarkedHEdge, 1]] = True

            # 粗化后单元的编号: NC:NC+nn 
            nidxmap = np.arange(NN)
            nidxmap[isRNode] = range(NC, NC+nn)
            cidxmap = np.arange(NC+1)
            cidxmap[NC] = NC + nn
            isRHEdge = isRNode[halfedge[:, 0]]
            cidxmap[halfedge[isRHEdge, 1]] = nidxmap[halfedge[isRHEdge, 0]]
            halfedge[:, 1] = cidxmap[halfedge[:, 1]]
            nlevel = np.zeros(NN, dtype=self.itype)
            nlevel[halfedge[:, 0]] = hlevel
            level = nlevel[isRNode] - 1
            level[level < 0] = 0
            clevel = np.r_[clevel[:-1], level, 0]

            # 重设下一个半边 halfedge[:, 2] 和前一个半边 halfedge[:, 3]
            nex = halfedge[:, 2] # 当前半边的下一个半边编号
            flag = isRNode[halfedge[nex, 0]] # 如果下一个半边的指向的节点是要移除的节点
            # 当前半边的下一个半边修改为:下一个半边的对偶半边的下一个半边
            halfedge[flag, 2] = halfedge[halfedge[nex[flag], 4], 2]
            # 下一个半边的前一个半边是当前半边
            halfedge[halfedge[flag, 2], 3], = np.nonzero(flag) 

            nidxmap = np.zeros(NN, dtype=self.itype)
            # 标记进一步要移除的半边
            idx = np.arange(2*NE)
            flag = ~isMarkedHEdge
            flag = flag & (halfedge[halfedge[halfedge[halfedge[:, 2], 4], 2], 4] == idx)
            flag = flag & (hlevel > hlevel[halfedge[:, 2]])
            flag = flag & (hlevel > hlevel[halfedge[:, 3]])

            nex = halfedge[flag, 2]
            pre = halfedge[flag, 3]
            dua = halfedge[flag, 4]

            halfedge[pre, 2] = nex
            halfedge[nex, 3] = pre
            halfedge[nex, 4] = dua

            isMarkedHEdge[flag] = True
            isRNode[halfedge[flag, 0]] = True
            NN -= nn + flag.sum()//2

            # 对节点重新编号
            nidxmap[~isRNode] = range(NN)
            halfedge[:, 0] = nidxmap[halfedge[:, 0]]

            # 对半边重新编号
            ne = sum(~isMarkedHEdge)
            eidxmap = np.arange(2*NE)
            eidxmap[~isMarkedHEdge] = range(ne)
            halfedge = halfedge[~isMarkedHEdge]
            halfedge[:, 2:5] = eidxmap[halfedge[:, 2:5]]

            # 对单元重新编号
            isKeepedCell = np.zeros(NC+nn+1, dtype=np.bool)
            isKeepedCell[halfedge[:, 1]] = True
            cidxmap = np.zeros(NC+nn+1, dtype=self.itype)
            NC = sum(isKeepedCell)
            cidxmap[isKeepedCell] = range(NC)
            halfedge[:, 1] = cidxmap[halfedge[:, 1]]

            # 更新层信息
            self.halfedgedata['level'] = hlevel[~isMarkedHEdge] 
            self.celldata['level'] = clevel[~isMarkedCell]

            # 更新节点和半边数据结构信息
            self.node = self.node[~isRNode]
            self.ds.reinit(NN, NC-1, halfedge)

    def refine_marker(self, eta, theta, method="L2"):
        NC = self.number_of_cells()
        isMarkedCell = np.zeros(NC+1, dtype=np.bool)
        isMarkedCell[:-1] = mark(eta, theta, method=method)
        return isMarkedCell

    def add_halfedge_plot(self, axes,
        index=None, showindex=False,
        nodecolor='r', edgecolor=['r', 'k'], markersize=20,
        fontsize=8, fontcolor='k', multiindex=None, linewidth=0.5):

        show_halfedge_mesh(axes, self,
                index=index, showindex=showindex,
                nodecolor=nodecolor, edgecolor=edgecolor, markersize=markersize,
                fontsize=fontsize, fontcolor=fontcolor, 
                multiindex=multiindex, linewidth=linewidth)

    def print(self):
        cell, cellLocation = self.entity('cell')
        print("cell:\n", cell)
        print("cellLocation:\n", cellLocation)
        print("cell2edge:\n", self.ds.cell_to_edge(sparse=False))
        print("cell2hedge:\n")
        for i, val in enumerate(self.ds.cell2hedge[:-1]):
            print(i, ':', val)

        print("edge:")
        for i, val in enumerate(self.entity('edge')):
            print(i, ":", val)

class HalfEdgeMesh2dDataStructure():
    def __init__(self, NN, NC, halfedge):
        self.NN = NN
        self.NC = NC
        self.NE = len(halfedge)//2
        self.NF = self.NE
        self.halfedge = halfedge
        self.itype = halfedge.dtype

        self.cell2hedge = np.zeros(NC+1, dtype=self.itype)
        self.cell2hedge[halfedge[:, 1]] = range(2*self.NE)

    def reinit(self, NN, NC, halfedge):
        self.NN = NN
        self.NC = NC
        self.NE = len(halfedge)//2
        self.NF = self.NE
        self.halfedge = halfedge
        self.itype = halfedge.dtype

        self.cell2hedge = np.zeros(NC+1, dtype=self.itype)
        self.cell2hedge[halfedge[:, 1]] = range(2*self.NE)

    def number_of_vertices_of_cells(self, returnall=False):
        NC = self.NC
        halfedge = self.halfedge
        NV = np.zeros(NC+1, dtype=self.itype)
        np.add.at(NV, halfedge[:, 1], 1)
        if returnall:
            return NV
        else:
            return NV[:NC]

    def number_of_nodes_of_cells(self):
        return self.number_of_vertices_of_cells()

    def number_of_edges_of_cells(self):
        return self.number_of_vertices_of_cells()

    def number_of_face_of_cells(self):
        return self.number_of_vertices_of_cells()

    def cell_to_node(self, sparse=True):
        NN = self.NN
        NC = self.NC
        NE = self.NE

        halfedge = self.halfedge
        isInHEdge = (halfedge[:, 1] != NC)

        if sparse:
            val = np.ones(isInHEdge.sum(), dtype=np.bool)
            I = halfedge[isInHEdge, 1]
            J = halfedge[isInHEdge, 0]
            cell2node = csr_matrix((val, (I.flat, J.flat)), shape=(NC, NN), dtype=np.bool)
            return cell2node
        else:
            NV = self.number_of_vertices_of_cells()
            cellLocation = np.zeros(NC+1, dtype=self.itype)
            cellLocation[1:] = np.cumsum(NV)
            cell2node = np.zeros(cellLocation[-1], dtype=self.itype)
            current = self.cell2hedge.copy()[:NC]
            idx = cellLocation[:-1].copy()
            cell2node[idx] = halfedge[current, 0]
            NV0 = np.ones(NC, dtype=self.itype)
            isNotOK = NV0 < NV
            while isNotOK.sum() > 0:
               current[isNotOK] = halfedge[current[isNotOK], 2]
               idx[isNotOK] += 1
               NV0[isNotOK] += 1
               cell2node[idx[isNotOK]] = halfedge[current[isNotOK], 0]
               isNotOK = (NV0 < NV)
            return cell2node, cellLocation

    def cell_to_edge(self, sparse=False):
        NE = self.NE
        NC = self.NC

        halfedge = self.halfedge

        J = np.zeros(2*NE, dtype=self.itype)
        isMainHEdge = (halfedge[:, 5] == 1)
        J[isMainHEdge] = range(NE)
        J[halfedge[isMainHEdge, 4]] = range(NE)
        if sparse:
            isInHEdge = (halfedge[:, 1] != NC)
            val = np.ones(2*NE, dtype=np.bool)
            cell2edge = csr_matrix((val[isInHEdge], (halfedge[isInHEdge, 1],
                J[isInHEdge])), shape=(NC, NE), dtype=np.bool)
            return cell2edge
        else:
            NV = self.number_of_vertices_of_cells()
            cellLocation = np.zeros(NC+1, dtype=self.itype)
            cellLocation[1:] = np.cumsum(NV)
            cell2edge = np.zeros(cellLocation[-1], dtype=self.itype)
            current = halfedge[self.cell2hedge[:-1], 2] # 下一个边
            idx = cellLocation[:-1]
            cell2edge[idx] = J[current]
            NV0 = np.ones(NC, dtype=self.itype)
            isNotOK = NV0 < NV
            while isNotOK.sum() > 0:
                current[isNotOK] = halfedge[current[isNotOK], 2]
                idx[isNotOK] += 1
                NV0[isNotOK] += 1
                cell2edge[idx[isNotOK]] = J[current[isNotOK]]
                isNotOK = (NV0 < NV)
            return cell2edge

    def cell_to_face(self, sparse=True):
        return self.cell_to_edge(sparse=sparse)

    def cell_to_cell(self):
        NC = self.NC
        halfedge = self.halfedge
        isInHEdge = (halfedge[:, 1] != NC)
        val = np.ones(isInHEdge.sum(), dtype=np.bool)
        I = halfedge[isInHEdge, 1]
        J = halfedge[halfedge[isInHEdge, 4], 1]
        cell2cell = coo_matrix((val, (I, J)), shape=(NC, NC), dtype=np.bool)
        cell2cell+= coo_matrix((val, (J, I)), shape=(NC, NC), dtype=np.bool)
        return cell2cell.tocsr()

    def edge_to_node(self, sparse=False):
        NN = self.NN
        NE = self.NE
        halfedge = self.halfedge
        isMainHEdge = halfedge[:, 5] == 1
        if sparse == False:
            edge = np.zeros((NE, 2), dtype=self.itype)
            edge[:, 0] = halfedge[halfedge[isMainHEdge, 4], 0]
            edge[:, 1] = halfedge[isMainHEdge, 0]
            return edge
        else:
            val = np.ones((NE,), dtype=np.bool)
            edge2node = coo_matrix((val, (range(NE), halfedge[isMainHEdge,0])), shape=(NE, NN), dtype=np.bool)
            edge2node+= coo_matrix((val, (range(NE), halfedge[halfedge[isMainHEdge, 4], 0])), shape=(NE, NN), dtype=np.bool)
            return edge2node.tocsr()

    def edge_to_edge(self):
        edge2node = self.edge_to_node()
        return edge2node*edge2node.tranpose()

    def edge_to_cell(self, sparse=False):
        NE = self.NE
        NC = self.NC
        halfedge = self.halfedge

        J = np.zeros(2*NE, dtype=self.itype)
        isMainHEdge = (halfedge[:, 5] == 1)
        J[isMainHEdge] = range(NE)
        J[halfedge[isMainHEdge, 4]] = range(NE)
        if sparse:
            isInHEdge = (halfedge[:, 1] != NC)
            val = np.ones(2*NE, dtype=np.bool)
            edge2cell = csr_matrix((val[isInHEdge], (J[isInHEdge], halfedge[isInHEdge, 1])), shape=(NE, NC), dtype=np.bool)
            return edge2cell
        else:
            edge2cell = np.zeros((NE, 4), dtype=self.itype)
            edge2cell[J[isMainHEdge], 0] = halfedge[isMainHEdge, 1]
            edge2cell[J[halfedge[isMainHEdge, 4]], 1] = halfedge[halfedge[isMainHEdge, 4], 1]

            current = halfedge[self.cell2hedge[:-1], 2] # 下一个边
            end = current.copy()
            lidx = np.zeros_like(current)
            isNotOK = np.ones_like(current, dtype=np.bool)
            while np.any(isNotOK):
                idx = J[current[isNotOK]]
                flag = (halfedge[current[isNotOK], 5] == 1)
                edge2cell[idx[flag], 2] = lidx[isNotOK][flag]
                edge2cell[idx[~flag], 3] = lidx[isNotOK][~flag]
                current[isNotOK] = halfedge[current[isNotOK], 2]
                lidx[isNotOK] += 1
                isNotOK = (current != end)

            isBdEdge = (edge2cell[:, 1] == NC)
            edge2cell[isBdEdge, 1] = edge2cell[isBdEdge, 0]
            edge2cell[isBdEdge, 3] = edge2cell[isBdEdge, 2]
            return edge2cell

    def node_to_node(self):
        NN = self.NN
        NE = self.NE

        edge = self.edge_to_node()
        I = edge[:, 0:2].flat
        J = edge[:, 1::-1].flat
        val = np.ones(2*NE, dtype=np.bool)
        node2node = csr_matrix((val, (I, J)), shape=(NN, NN), dtype=np.bool)
        return node2node

    def node_to_cell(self, sparse=True):

        NN = self.NN
        NC = self.NC
        NE = self.NE

        isInHEdge = (halfedge[:, 1] != NC)
        val = np.ones(isInHEdge.sum(), dtype=np.bool)
        I = halfedge[isInHEdge, 0]
        J = halfedge[isInHEdge, 1]
        cell2node = csr_matrix((val, (I.flat, J.flat)), shape=(NC, NN), dtype=np.bool)
        return node2cell


    def boundary_node_flag(self):
        NN = self.NN
        edge = self.edge_to_node()
        isBdEdge = self.boundary_edge_flag()
        isBdNode = np.zeros(NN, dtype=np.bool)
        isBdNode[edge[isBdEdge,:]] = True
        return isBdNode

    def boundary_edge_flag(self):
        NE = self.NE
        edge2cell = self.edge_to_cell()
        return edge2cell[:, 0] == edge2cell[:, 1]

    def boundary_edge(self):
        edge = self.edge_to_node()
        return edge[self.boundary_edge_index()]

    def boundary_cell_flag(self):
        NC = self.NC
        edge2cell = self.edge_to_cell()
        isBdEdge = edge2cell[:, 0] == edge2cell[:, 1]
        isBdCell = np.zeros(NC, dtype=np.bool)
        isBdCell[edge2cell[isBdEdge, 0:2]] = True
        return isBdCell

    def boundary_node_index(self):
        isBdNode = self.boundary_node_flag()
        idx, = np.nonzero(isBdNode)
        return idx

    def boundary_edge_index(self):
        isBdEdge = self.boundary_edge_flag()
        idx, = np.nonzero(isBdEdge)
        return idx

    def boundary_cell_index(self):
        isBdCell = self.boundary_cell_flag()
        idx, = np.nonzero(isBdCell)
        return idx