import os 
import numpy as np

from scipy.sparse.linalg import lgmres


class LSSolver():
    def __init__(self, space):
        self.space = space

    def output(self, phi, u, timestep, output_dir, filename_prefix):
        mesh = self.space.mesh
        if output_dir != 'None':
            mesh.nodedata['phi'] = phi
            mesh.nodedata['velocity'] = u
            fname = os.path.join(output_dir, f'{filename_prefix}_{timestep:010}.vtu')
            mesh.to_vtk(fname=fname)

    def check_gradient_norm_at_interface(self, phi, tolerance=1e-3):
        """
        Check the gradient magnitude of the level set function at the interface.

        Parameters:
        - phi: The level set function evaluated at quadrature points.
        - tolerance: The tolerance within which a point is considered part of the interface.

        Returns:
        - diff_avg: The average difference between the gradient magnitude and 1 at the interface.
        - diff_max: The maximum difference between the gradient magnitude and 1 at the interface.
        """
        # Compute phi and the gradient of phi at quadrature points
        mesh = self.space.mesh
        qf = mesh.integrator(3)
        bcs, _ = qf.get_quadrature_points_and_weights()
        phi_quad = self.space.value(uh=phi, bc=bcs)
        grad_phi_quad = self.space.grad_value(uh=phi, bc=bcs)

        # Compute the magnitude of the gradient at quadrature points
        magnitude = np.linalg.norm(grad_phi_quad, axis=-1)

        # Identify points at the interface
        at_interface_mask = np.abs(phi_quad) <= tolerance

        # Compute the difference between the magnitude and 1 at the interface
        diff = np.abs(magnitude[at_interface_mask]) - 1

        diff_avg = np.mean(diff) if np.any(at_interface_mask) else 0
        diff_max = np.max(diff) if np.any(at_interface_mask) else 0

        return diff_avg, diff_max

    class IterationCounter(object):
        def __init__(self, disp=True):
            self._disp = disp
            self.niter = 0

        def __call__(self, rk=None):
            self.niter += 1
            if self._disp:
                print('iter %3i' % (self.niter))

    def solve_system(self, A, b, tol=1e-8):
        counter = self.IterationCounter(disp = False)
        result, _ = lgmres(A, b, tol = tol, atol = tol, callback = counter)

        return result

    def compute_zero_level_set_area(self, phi0):
        """
        Compute the area of the zero level set of the level set function.

        Parameters:
        - phi0: The level set function evaluated at grid points.

        Returns:
        - area: The computed area of the zero level set.
        """
        mesh = self.space.mesh
        measure = self.space.function()
        measure[phi0 > 0] = 0
        measure[phi0 <= 0] = 1
        
        qf = mesh.integrator(3)
        bcs, ws = qf.get_quadrature_points_and_weights()
        cellmeasure = mesh.entity_measure('cell')
        
        area = np.einsum('i, ij, j ->', ws, measure(bcs), cellmeasure)

        return area
