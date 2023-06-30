#!/usr/bin/env python3
# 

import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.sparse.linalg import spsolve

from fealpy.pde.poisson_2d import CosCosData
from fealpy.functionspace import LagrangeFESpace
from fealpy.fem import ScalarLaplaceIntegrator      # (\nabla u, \nabla v) 
from fealpy.fem import ScalarSourceIntegrator         # (f, v)
from fealpy.fem import ScalarNeumannSourceIntegrator  # <g_D, v>
from fealpy.fem import ScalarRobinSourceIntegrator    # <g_R, v>
from fealpy.fem import ScalarRobinBoundaryIntegrator  # <kappa*u, v>

from fealpy.fem import BilinearForm
from fealpy.fem import LinearForm
from fealpy.fem import DirichletBC

from fealpy.solver import GAMGSolver

import ipdb

## 参数解析
parser = argparse.ArgumentParser(description=
        """
        QuadrangleMesh 上任意次有限元方法
        """)

parser.add_argument('--degree',
        default=1, type=int,
        help='Lagrange 有限元空间的次数, 默认为 1 次.')

parser.add_argument('--mtype',
        default='tri', type=str,
        help='网格类型 tri 或者 quad, 默认为 tri.')

parser.add_argument('--nx',
        default=8, type=int,
        help='初始网格剖分段数.')

parser.add_argument('--ny',
        default=8, type=int,
        help='初始网格剖分段数.')

parser.add_argument('--maxit',
        default=4, type=int,
        help='默认网格加密求解的次数, 默认加密求解 4 次')

args = parser.parse_args()

p = args.degree
mtype = args.mtype
nx = args.nx
ny = args.ny
maxit = args.maxit

pde = CosCosData(kappa=1.0)
domain = pde.domain()

if mtype == 'tri':
    from fealpy.mesh import TriangleMesh
    mesh = TriangleMesh.from_box(domain, nx=nx, ny=ny)
elif mtype == 'quad':
    from fealpy.mesh import QuadrangleMesh
    mesh = QuadrangleMesh.from_box(domain, nx=nx, ny=ny)


errorType = ['$|| u - u_h||_{\Omega,0}$', 
        '$||\\nabla u - \\nabla u_h||_{\Omega, 0}$']
errorMatrix = np.zeros((2, maxit), dtype=np.float64)
NDof = np.zeros(maxit, dtype=np.int_)

for i in range(maxit):
    print("The {}-th computation:".format(i))
    space = LagrangeFESpace(mesh, p=p)
    NDof[i] = space.number_of_global_dofs()

    bform = BilinearForm(space)
    # (\nabla u, \nabla v)
    bform.add_domain_integrator(ScalarLaplaceIntegrator(q=p+2)) 
    # <kappa u, v>
    rbi = ScalarRobinBoundaryIntegrator(pde.kappa,
            threshold=pde.is_robin_boundary, q=p+2)
    bform.add_boundary_integrator(rbi) 
    A = bform.assembly()

    lform = LinearForm(space)
    # (f, v)
    si = ScalarSourceIntegrator(pde.source, q=p+2)
    lform.add_domain_integrator(si)
    # <g_R, v> 
    rsi = ScalarRobinSourceIntegrator(pde.robin, threshold=pde.is_robin_boundary, q=p+2)
    lform.add_boundary_integrator(rsi)
    # <g_N, v>
    nsi = ScalarNeumannSourceIntegrator(pde.neumann, 
            threshold=pde.is_neumann_boundary, q=p+2)
    lform.add_boundary_integrator(nsi)
    #ipdb.set_trace()
    F = lform.assembly()

    # Dirichlet 边界条件
    bc = DirichletBC(space, 
            pde.dirichlet, threshold=pde.is_dirichlet_boundary) 
    uh = space.function() 
    A, F = bc.apply(A, F, uh)

    solver = GAMGSolver(ptype='W', sstep=3)
    solver.setup(A)
    uh[:] = solver.solve(F)

    errorMatrix[0, i] = mesh.error(pde.solution, uh, q=p+2)
    errorMatrix[1, i] = mesh.error(pde.gradient, uh.grad_value, q=p+2)

    if i < maxit-1:
        mesh.uniform_refine()

print(errorMatrix)
print(errorMatrix[:, 0:-1]/errorMatrix[:, 1:])
