#cython: language_level=3

from qutip.core.data.csr cimport CSR

cpdef double complex inner_csr(CSR left, CSR right, bint scalar_is_ket=*) nogil
