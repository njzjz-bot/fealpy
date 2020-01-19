import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, bmat, spdiags

from ..functionspace import WeakGalerkinSpace2d
from ..boundarycondition import BoundaryCondition

class SobolevEquationWGModel2d:
    """
    Solve Sobolev equation by weak Galerkin method.

    """
    def __init__(self, pde, mesh, p, q=None):
        self.pde = pde
        self.mesh = mesh
        self.space = WeakGalerkinSpace2d(mesh, p=p, q=q)
        self.construct_marix()

    def init_solution(self, timeline):
        NL = timeline.number_of_time_levels()
        gdof = self.space.number_of_global_dofs()
        uh = self.space.function(dim=NL)
        uh[:, 0] = self.space.project(lambda x: self.pde.solution(x, 0.0))
        return uh

    def construct_marix(self):
        """
        构造 Soblove 方程对应的所有矩阵
        """
        gdof = self.space.number_of_global_dofs()
        cell2dof, cell2dofLocation = self.space.cell_to_dof()
        cd = np.hsplit(cell2dof, cell2dofLocation[1:-1])
        H0 = self.space.H0
        R = self.space.R
        def f0(i):
            R0 = R[0][:, cell2dofLocation[i]:cell2dofLocation[i+1]]
            R1 = R[1][:, cell2dofLocation[i]:cell2dofLocation[i+1]]
            return R0.T@H0[i]@R0, R1.T@H0[i]@R1, R0.T@H0[i]@R1

        NC = self.mesh.number_of_cells()
        M = list(map(f0, range(NC)))

        idx = list(map(np.meshgrid, cd, cd))
        I = np.concatenate(list(map(lambda x: x[1].flat, idx)))
        J = np.concatenate(list(map(lambda x: x[0].flat, idx)))

        val = np.concatenate(list(map(lambda x: x[0].flat, M)))
        M00 = csr_matrix((val, (I, J)), shape=(gdof, gdof))

        val = np.concatenate(list(map(lambda x: x[1].flat, M)))
        M11 = csr_matrix((val, (I, J)), shape=(gdof, gdof))

        val = np.concatenate(list(map(lambda x: x[2].flat, M)))
        M01 = csr_matrix((val, (I, J)), shape=(gdof, gdof))


        self.D = bmat([[M00, M01], [M01.T, M11]], format='csr') # weak divergence matrix
        self.G = M00 + M11 # weak gradient matrix

        self.S = self.space.stabilizer_matrix()
        self.M = self.space.mass_matrix()

        M0 = self.M/self.pde.mu
        self.A1 = self.D + bmat([[self.S, None], [None, self.S]], format='csr') + bmat([[M0, None], [None, M0]], format='csr')
        self.A2 = self.G + self.S

        c2d = self.space.cell_to_dof(doftype='cell')
        idx = list(map(np.meshgrid, cd, c2d))
        I = np.concatenate(list(map(lambda x: x[1].flat, idx)))
        J = np.concatenate(list(map(lambda x: x[0].flat, idx)))
        def f1(i, j):
            Rj = R[j][:, cell2dofLocation[i]:cell2dofLocation[i+1]]
            return Rj.flat
        val = np.concatenate(list(map(lambda i: f1(i, 0), range(NC))))
        B0 = csr_matrix((val, (I, J)), shape=(gdof, gdof))
        val = np.concatenate(list(map(lambda i: f1(i, 1), range(NC))))
        B1 = csr_matrix((val, (I, J)), shape=(gdof, gdof))
        self.B = bmat([[B0], [B1]], format='csr')

    def project(self, u, timeline):
        NL = timeline.number_of_time_levels()
        gdof = self.space.number_of_global_dofs()
        uh = self.space.function(dim=NL)
        times = timeline.all_time_levels()
        for i, t in enumerate(times):
            uh[:, i] = self.space.project(lambda x:u(x, t))
        return uh

    def get_current_left_matrix(self, timeline):
        mu = self.pde.mu
        epsilon = self.pde.epsilon
        dt = timeline.current_time_step_length()
        D = self.A1
        G = self.A2
        B = -dt*epsilon/mu*self.B
        return bmat([[dt*D, B], [B.T, epsilon*(1 + dt*epsilon/mu)*G]], format='csr')

    def get_current_right_vector(self, data, timeline):
        mu = self.pde.mu
        epsilon = self.pde.epsilon

        i = timeline.current
        dt = timeline.current_time_step_length()
        R = self.space.R

        uh = data[0]
        ph = data[1]
        solver = data[2]

        cell2dof, cell2dofLocation = self.space.cell_to_dof(doftype='all')
        cd = np.hsplit(cell2dof, cell2dofLocation[1:-1])

        NC = self.mesh.number_of_cells()
        gdof = self.space.number_of_global_dofs()
        c2d = self.space.cell_to_dof(doftype='cell') # only get the dofs in cell

        # -(f, \nabla\cdot \bfq)
        t1 = timeline.next_time_level()
        fh = self.space.project(lambda x: self.pde.source(x, t1))
        F = np.zeros((gdof, 3), dtype=self.space.ftype)
        f10 = lambda j: fh[c2d[j]]@R[0][:, cell2dofLocation[j]:cell2dofLocation[j+1]]
        f11 = lambda j: fh[c2d[j]]@R[1][:, cell2dofLocation[j]:cell2dofLocation[j+1]]
        np.subtract.at(F[:, 0], cell2dof, np.concatenate(list(map(f10, range(NC)))))
        np.subtract.at(F[:, 1], cell2dof, np.concatenate(list(map(f11, range(NC)))))
        F[:, 0:2] *= dt
        F[:, 2] = epsilon*self.A2@uh[:, i]
        return F.T.flat

    def solve(self, data, A, b, solver, timeline):
        uh = data[0]
        ph = data[1]
        i = timeline.current
        # deal with dirichlet boundary condition 
        t1 = timeline.next_time_level()
        dirichlet = lambda x: self.pde.dirichlet(x, t1)
        isDDof = self.space.set_dirichlet_bc(uh[:, i+1], dirichlet)
        gdof = self.space.number_of_global_dofs()
        flag = np.zeros(gdof, dtype=np.bool)
        isDDof = np.r_[flag, flag, isDDof]

        x = np.zeros(3*gdof, dtype=self.space.ftype)
        x[2*gdof:] = uh[:, i+1]
        b -= A@x
        bdIdx = np.zeros(3*gdof, dtype=np.int)
        bdIdx[isDDof] = 1
        Tbd = spdiags(bdIdx, 0, 3*gdof, 3*gdof)
        T = spdiags(1-bdIdx, 0, 3*gdof, 3*gdof)
        A = T@A@T + Tbd
        b[isDDof] = x[isDDof]

        x[:] = solver(A, b)
        phi = self.space.function(dim=2)
        phi[:, 0] = x[:gdof]
        phi[:, 1] = x[gdof:2*gdof]
        uh[:, i+1] = x[2*gdof:]

        ph.append(phi)

    def error(self, data, timeline):
        pde = self.pde
        uh = data[0]
        ph = data[1]

        integralalg = self.space.integralalg
        NL = timeline.number_of_time_levels()
        gdof = self.space.number_of_global_dofs()
        times = timeline.all_time_levels()
        error0 = 0.0
        error1 = 0.0
        error2 = 0.0
        error3 = 0.0
        for i, t in enumerate(times[:-1]):
            uhi = uh.index(i+1)
            dt = times[i+1] - times[i]

            e0 = integralalg.L2_error(lambda x: pde.solution(x, t+dt), uhi)
            error0 += dt*e0*e0

            e1 = integralalg.L2_error(lambda x: pde.flux(x, t+dt), ph[i+1])
            error1 += dt*e1*e1

            guhi = self.space.weak_grad(uhi)
            e2 = integralalg.L2_error(lambda x: pde.gradient(x, t+dt), guhi)
            error2 += dt*e2*e2

            dphi = self.space.weak_div(ph[i+1])
            e3 = integralalg.L2_error(lambda x: pde.div_flux(x, t+dt), dphi)
            error3 += dt*e3*e3
        return np.sqrt(error0), np.sqrt(error1), np.sqrt(error2), np.sqrt(error3)

    def get_current_left_matrix_1(self, timeline):
        return self.A2

    def get_current_right_vector_1(self, data, timeline):
        mu = self.pde.mu
        epsilon = self.pde.epsilon

        uh = data[0]
        ph = data[1]
        solver = data[2]
        i = timeline.current

        t1 = timeline.next_time_level()
        fh = self.space.project(lambda x: self.pde.source(x, t1))
        cell2dof, cell2dofLocation = self.space.cell_to_dof(doftype='all')
        cd = np.hsplit(cell2dof, cell2dofLocation[1:-1])

        NC = self.mesh.number_of_cells()
        gdof = self.space.number_of_global_dofs()
        c2d = self.space.cell_to_dof(doftype='cell') # only get the dofs in cell
        # (\nabla u, \bfq)
        F0 = np.zeros((gdof, 2), dtype=self.space.ftype)
        R = self.space.R
        f00 = lambda j: R[0][:, cell2dofLocation[j]:cell2dofLocation[j+1]]@uh[cd[j], i]
        f01 = lambda j: R[1][:, cell2dofLocation[j]:cell2dofLocation[j+1]]@uh[cd[j], i]
        F0[c2d, 0] = list(map(f00, range(NC)))
        F0[c2d, 1] = list(map(f01, range(NC)))

        # -(f, \nabla\cdot \bfq)
        F1 = np.zeros((gdof, 2), dtype=self.space.ftype)
        f10 = lambda j: fh[c2d[j, :]]@R[0][:, cell2dofLocation[j]:cell2dofLocation[j+1]]
        f11 = lambda j: fh[c2d[j, :]]@R[1][:, cell2dofLocation[j]:cell2dofLocation[j+1]]
        np.add.at(F1[:, 0], cell2dof, np.concatenate(list(map(f10, range(NC)))))
        np.add.at(F1[:, 1], cell2dof, np.concatenate(list(map(f11, range(NC)))))


        F = epsilon/mu*F0 - F1
        phi = self.space.function(dim=2)
        phi.T.flat = solver(self.A1, np.asarray(F.T.flat))
        ph.append(phi)

        dt = timeline.current_time_step_length()
        t0 = timeline.current_time_level()
        F = (1- dt*epsilon/mu)*(self.A2@uh[:, i])

        f20 = lambda j: phi[c2d[j, :], 0]@R[0][:, cell2dofLocation[j]:cell2dofLocation[j+1]]
        f22 = lambda j: phi[c2d[j, :], 1]@R[1][:, cell2dofLocation[j]:cell2dofLocation[j+1]]
        f = lambda j: dt*(f20(j) + f22(j))/mu
        np.add.at(F, cell2dof, np.concatenate(list(map(f, range(NC)))))
        return F

    def solve_1(self, data, A, b, solver, timeline):
        uh = data[0]
        i = timeline.current
        # deal with dirichlet boundary condition 
        t1 = timeline.next_time_level()
        dirichlet = lambda x: self.pde.dirichlet(x, t1)
        bc = BoundaryCondition(self.space, dirichlet=dirichlet)
        A, b = bc.apply_dirichlet_bc(A, b, uh[:, i+1])
        uh[:, i+1] = solver(A, b)


