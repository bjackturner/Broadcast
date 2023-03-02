
## Resolvent in python using PETSc functions

import numpy as _np
from mpi4py import MPI
import misc.PETSc_func as pet
from petsc4py import PETSc

import restart_init as ri

import timeit
import sys
import os

def resolvent(freq, wavenum, Jacs, Qq, Qvol2, Qvol2inv, P, Dz, Dzz):

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()

    eigenvalueL = []
    eigenvector_forcageL = []
    eigenvector_reponseL = []
    Nfreq = _np.shape(freq)[0]
    Nwave = _np.shape(wavenum)[0]
    for kk in range(Nwave):
        for k in range(Nfreq):
            A, ksp_R = pet.createShellResolvent3D_1B(Jacs, freq[k], wavenum[kk] ,Qq , Qvol2inv, P, Dz, Dzz)
            eigenvector_forcage = []
            t1 = timeit.time.time()
            #Solving du pb aux VP
            eigenvalue, eigenvector_forcage, eps =  pet.eigPetsc2(comm ,A ,Qvol2, P ,nev=1, tol=1.e-4, maxits=10)
            t2 = timeit.time.time()
            t_eig = t2 - t1

            eigenvector_reponse, eigenvector_forcageP = pet.computeReponse2(comm, eigenvalue, eigenvector_forcage ,ksp_R, P)
            eigenvector_reponseL.append(eigenvector_reponse)
            ksp_R.destroy()

            eigenvector_forcageL.append(eigenvector_forcageP)
            # eigenvector_forcageL.append(eigenvector_forcage)
            eigenvalueL.append(eigenvalue)
            if rank ==0:
                print('Frequency n', k+1)
                print('Time eig:', t_eig)

    comm.Barrier()
    return eigenvalueL, eigenvector_forcageL, eigenvector_reponseL



def computeQ_Ec(w, vol):

    im = _np.shape(w)[0]
    jm = _np.shape(w)[1]
    nbentry = im*jm*7
    Iq = _np.zeros((nbentry), dtype=_np.int32)
    Jq = _np.zeros((nbentry), dtype=_np.int32)
    valq = _np.zeros((nbentry))
    for i in range(im):
        for j in range(jm):
            current = j * 7 + i * jm*7
            Iq[current]   = j * 5 + i * jm*5
            Jq[current]   = j * 5 + i * jm*5
            valq[current] = 0.5*vol[i,j] * (w[i,j,1]**2 + w[i,j,2]**2) / w[i,j,0]**3
            Iq[current +1]   = j * 5 + i * jm*5
            Jq[current +1]   = j * 5 + i * jm*5 + 1
            valq[current +1] = 0.5*vol[i,j] * ( - w[i,j,1]) / w[i,j,0]**2
            Iq[current +2]   = j * 5 + i * jm*5
            Jq[current +2]   = j * 5 + i * jm*5 + 2
            valq[current +2] = 0.5*vol[i,j] * ( - w[i,j,2]) / w[i,j,0]**2
            Iq[current +3]   = j * 5 + i * jm*5 + 1
            Jq[current +3]   = j * 5 + i * jm*5
            valq[current +3] = 0.5*vol[i,j] * ( - w[i,j,1]) / w[i,j,0]**2
            Iq[current +4]   = j * 5 + i * jm*5 + 1
            Jq[current +4]   = j * 5 + i * jm*5 + 1
            valq[current +4] = 0.5*vol[i,j] * 1. / w[i,j,0]
            Iq[current +5]   = j * 5 + i * jm*5 + 2
            Jq[current +5]   = j * 5 + i * jm*5
            valq[current +5] = 0.5*vol[i,j] * ( - w[i,j,2]) / w[i,j,0]**2
            Iq[current +6]   = j * 5 + i * jm*5 + 2
            Jq[current +6]   = j * 5 + i * jm*5 + 2
            valq[current +6] = 0.5*vol[i,j] * 1. / w[i,j,0]
    # import matplotlib.pyplot as plt
    # import scipy.sparse as sp
    # Qq = sp.csc_matrix((valq,(Iq,Jq)), shape=(im*jm*5,im*jm*5))
    # plt.figure()
    # plt.spy(Qq)
    # plt.show()
    Qq = pet.createMatPetscCSR(Iq, Jq, valq, im*jm*5, im*jm*5, 3)

    return Qq


def computeQ_Echu(w, vol, gam, Mach):

    im = _np.shape(w)[0]
    jm = _np.shape(w)[1]
    nbentry = im*jm*17
    Iq = _np.zeros((nbentry), dtype=_np.int32)
    Jq = _np.zeros((nbentry), dtype=_np.int32)
    valq = _np.zeros((nbentry))
    for i in range(im):
        for j in range(jm):
            uu = w[i,j,1] / w[i,j,0]
            vv = w[i,j,2] / w[i,j,0]
            ee = w[i,j,4] / w[i,j,0] - 0.5 * (uu**2 + vv**2)
            TT = (gam - 1.) * gam * Mach**2 * ee
            a1 = (gam - 1.) * gam * Mach**2 * w[i,j,0] / TT
            a2 = (0.5 * (uu**2 + vv**2) - ee) / w[i,j,0]
            current = j * 17 + i * jm*17
            Iq[current]   = j * 5 + i * jm*5
            Jq[current]   = j * 5 + i * jm*5
            valq[current] = 0.5*vol[i,j] * ( (uu**2 + vv**2) / w[i,j,0] + TT / (w[i,j,0] * gam * Mach**2) + a1*a2**2 )
            Iq[current +1]   = j * 5 + i * jm*5
            Jq[current +1]   = j * 5 + i * jm*5 + 1
            valq[current +1] = 0.5*vol[i,j] * ( -uu * (1. + a1*a2) / w[i,j,0] )
            Iq[current +2]   = j * 5 + i * jm*5
            Jq[current +2]   = j * 5 + i * jm*5 + 2
            valq[current +2] = 0.5*vol[i,j] * ( -vv * (1. + a1*a2) / w[i,j,0] )
            Iq[current +3]   = j * 5 + i * jm*5
            Jq[current +3]   = j * 5 + i * jm*5 + 4
            valq[current +3] = 0.5*vol[i,j] * ( a1*a2 / w[i,j,0] )
            Iq[current +4]   = j * 5 + i * jm*5 + 1
            Jq[current +4]   = j * 5 + i * jm*5
            valq[current +4] = 0.5*vol[i,j] * ( -uu * (1. + a1*a2) / w[i,j,0] )
            Iq[current +5]   = j * 5 + i * jm*5 + 1
            Jq[current +5]   = j * 5 + i * jm*5 + 1
            valq[current +5] = 0.5*vol[i,j] * ( 1./w[i,j,0] + uu**2 * a1 / w[i,j,0]**2 )
            Iq[current +6]   = j * 5 + i * jm*5 + 1
            Jq[current +6]   = j * 5 + i * jm*5 + 2
            valq[current +6] = 0.5*vol[i,j] * ( uu * vv * a1 / w[i,j,0]**2 )
            Iq[current +7]   = j * 5 + i * jm*5 + 1
            Jq[current +7]   = j * 5 + i * jm*5 + 4
            valq[current +7] = 0.5*vol[i,j] * ( -uu * a1 / w[i,j,0]**2 )
            Iq[current +8]   = j * 5 + i * jm*5 + 2
            Jq[current +8]   = j * 5 + i * jm*5
            valq[current +8] = 0.5*vol[i,j] * ( -vv * (1. + a1*a2) / w[i,j,0] )
            Iq[current +9]   = j * 5 + i * jm*5 + 2
            Jq[current +9]   = j * 5 + i * jm*5 + 1
            valq[current +9] = 0.5*vol[i,j] * ( uu * vv * a1 / w[i,j,0]**2 )
            Iq[current +10]   = j * 5 + i * jm*5 + 2
            Jq[current +10]   = j * 5 + i * jm*5 + 2
            valq[current +10] = 0.5*vol[i,j] * ( 1./w[i,j,0] + vv**2 * a1 / w[i,j,0]**2 )
            Iq[current +11]   = j * 5 + i * jm*5 + 2
            Jq[current +11]   = j * 5 + i * jm*5 + 4
            valq[current +11] = 0.5*vol[i,j] * ( -vv * a1 / w[i,j,0]**2 )
            Iq[current +12]   = j * 5 + i * jm*5 + 3
            Jq[current +12]   = j * 5 + i * jm*5 + 3
            valq[current +12] = 0.5*vol[i,j] * ( 1./w[i,j,0] )
            Iq[current +13]   = j * 5 + i * jm*5 + 4
            Jq[current +13]   = j * 5 + i * jm*5 
            valq[current +13] = 0.5*vol[i,j] * ( a1*a2 / w[i,j,0] )
            Iq[current +14]   = j * 5 + i * jm*5 + 4
            Jq[current +14]   = j * 5 + i * jm*5 + 1
            valq[current +14] = 0.5*vol[i,j] * ( -uu * a1 / w[i,j,0]**2 )
            Iq[current +15]   = j * 5 + i * jm*5 + 4
            Jq[current +15]   = j * 5 + i * jm*5 + 2
            valq[current +15] = 0.5*vol[i,j] * ( -vv * a1 / w[i,j,0]**2 )
            Iq[current +16]   = j * 5 + i * jm*5 + 4
            Jq[current +16]   = j * 5 + i * jm*5 + 4
            valq[current +16] = 0.5*vol[i,j] * ( a1 / w[i,j,0]**2 )
    # import matplotlib.pyplot as plt
    # import scipy.sparse as sp
    # Qchu = sp.csc_matrix((valq,(Iq,Jq)), shape=(im*jm*5,im*jm*5))
    # plt.figure()
    # plt.spy(Qchu)
    # plt.show()
    Qchu = pet.createMatPetscCSR(Iq, Jq, valq, im*jm*5, im*jm*5, 5)

    return Qchu


def computeQ_L2(vol):

    im = _np.shape(vol)[0]
    jm = _np.shape(vol)[1]
    nbentry = im*jm*5
    Iq = _np.zeros((nbentry), dtype=_np.int32)
    Jq = _np.zeros((nbentry), dtype=_np.int32)
    valq2 = _np.zeros((nbentry))
    valq2inv = _np.zeros((nbentry))
    for i in range(im):
        for j in range(jm):
            for k in range(5):
                current = k + j * 5 + i * jm*5
                Iq[current]   = k + j * 5 + i * jm*5
                Jq[current]   = k + j * 5 + i * jm*5
                valq2[current] = vol[i,j]
                valq2inv[current] = 1./vol[i,j]
    # import matplotlib.pyplot as plt
    # import scipy.sparse as sp
    # Qvol2 = sp.csc_matrix((valq2,(Iq,Jq)), shape=(im*jm*5,im*jm*5))
    # plt.figure()
    # plt.spy(Qvol2)
    # plt.show()
    Qvol2    = pet.createMatPetscCSR(Iq, Jq, valq2, im*jm*5, im*jm*5, 1)
    Qvol2inv = pet.createMatPetscCSR(Iq, Jq, valq2inv, im*jm*5, im*jm*5, 1)

    return Qvol2, Qvol2inv
    

def computeP_everywhere_momentum(im, jm):
	### Restriction matrix P everywhere in space but applied only on momentum equations

    nbentry = im*jm*3
    Ip = _np.zeros((nbentry), dtype=_np.int32)
    Jp = _np.zeros((nbentry), dtype=_np.int32)
    valp = _np.zeros((nbentry))
    for i in range(im):
        for j in range(jm):
            for k in range(3):
                current = k + j * 3 + i * jm*3
                Ip[current]   = k+1 + j * 5 + i * jm*5
                Jp[current]   = k + j * 3 + i * jm*3
                valp[current] = 1.
    # import matplotlib.pyplot as plt
    # import scipy.sparse as sp
    # P = sp.csc_matrix((valp,(Ip,Jp)), shape=(im*jm*5,im*jm*3))
    # plt.figure()
    # plt.spy(P)
    # plt.show()
    P = pet.createMatPetscCSR(Ip, Jp, valp, im*jm*5, im*jm*3, 1)

    return P

def computeP_everywhere(im, jm, equations):
    ### Restriction matrix P everywhere in space, applied only on the list of equations given
    ### 0 = Continuity , 1 = Momentum X , 2 = Momentum Y , 3 = Momentum Z , 4 = Total energy
    ### example: momentum equations -> equations=[1, 2, 3]

    nequ = len(equations)
    nbentry = im*jm*nequ
    Ip = _np.zeros((nbentry), dtype=_np.int32)
    Jp = _np.zeros((nbentry), dtype=_np.int32)
    valp = _np.zeros((nbentry))
    for i in range(im):
        for j in range(jm):
            for k in range(nequ):
                current = k + j * nequ + i * jm*nequ
                Ip[current]   = equations[k] + j * 5 + i * jm*5
                Jp[current]   = k + j * nequ + i * jm*nequ
                valp[current] = 1.
    # import matplotlib.pyplot as plt
    # import scipy.sparse as sp
    # P = sp.csc_matrix((valp,(Ip,Jp)), shape=(im*jm*5,im*jm*nequ))
    # plt.figure()
    # plt.spy(P)
    # plt.show()
    P = pet.createMatPetscCSR(Ip, Jp, valp, im*jm*5, im*jm*nequ, 1)

    return P    

def computeQ_L2_control(vol):

    im = _np.shape(vol)[0]
    j = 0
    nbentry = im
    Iq = _np.zeros((nbentry), dtype=_np.int32)
    Jq = _np.zeros((nbentry), dtype=_np.int32)
    valq2 = _np.zeros((nbentry))
    for i in range(im):
        current = i
        Iq[current]   = i
        Jq[current]   = i
        valq2[current] = vol[i,j]

    Qvol2    = pet.createMatPetscCSR(Iq, Jq, valq2, im, im, 1)

    return Qvol2

def restrix(im, jm, nbeq, xc, yc, xmin, xmax, ymin, ymax, square=True):
    ### Restriction in space, compute a square matrix for square='True' (only zeros in the columns outside the zone)
    ### Compute a rectangular matrix for square='False' (there is exactly one 1 in each column)

    if square:
        nbentry = im*jm*nbeq
        Ir = _np.zeros((nbentry), dtype=_np.int32)
        Jr = _np.zeros((nbentry), dtype=_np.int32)
        valr = _np.zeros((nbentry))
        for i in range(im):
            for j in range(jm):
                for k in range(nbeq):
                    current = k + j * nbeq + i * jm*nbeq
                    Ir[current]   = k + j * nbeq + i * jm*nbeq
                    Jr[current]   = k + j * nbeq + i * jm*nbeq
                    if xc[i,j] < xmin:
                        valr[current] = 0.
                    elif xc[i,j] > xmax:
                        valr[current] = 0.
                    elif yc[i,j] < ymin:
                        valr[current] = 0.
                    elif yc[i,j] > ymax:
                        valr[current] = 0.
                    else:
                        valr[current] = 1.
        # import matplotlib.pyplot as plt
        # import scipy.sparse as sp
        # R = sp.csc_matrix((valr,(Ir,Jr)), shape=(im*jm*nbeq,im*jm*nbeq))
        # plt.figure()
        # plt.spy(R)
        # plt.show()
        Restrix = pet.createMatPetscCSR(Ir, Jr, valr, im*jm*nbeq, im*jm*nbeq, 1)

    else:
        nbentry = im*jm*nbeq
        Ir = _np.zeros((nbentry), dtype=_np.int32)
        Jr = _np.zeros((nbentry), dtype=_np.int32)
        valr = _np.zeros((nbentry))
        n_remove_i = 0
        current = -1
        for i in range(im):
            n_remove_j = 0
            if i==0:
                n_remove_j_tot = 0
                for j in range(jm):
                    if yc[0,j] < ymin:
                        n_remove_j_tot += 1
                    elif yc[0,j] > ymax:
                        n_remove_j_tot += 1
            if xc[i,0] < xmin:
                n_remove_i += 1
            elif xc[i,0] > xmax:
                n_remove_i += 1
            else:    
                for j in range(jm):
                    if yc[i,j] < ymin:
                        n_remove_j += 1
                    elif yc[i,j] > ymax:
                        n_remove_j += 1
                    else:
                        for k in range(nbeq):
                            current += 1
                            Ir[current]   = k + j * nbeq + i * jm*nbeq
                            Jr[current]   = k + (j - n_remove_j) * nbeq + (i - n_remove_i) * (jm - n_remove_j_tot)*nbeq
                            valr[current] = 1.
        nbentry_now = (im - n_remove_i) * (jm - n_remove_j_tot)*nbeq
        # print nbentry
        # print nbentry_now
        Ir = Ir[:nbentry_now]
        Jr = Jr[:nbentry_now]
        valr = valr[:nbentry_now]
        # import matplotlib.pyplot as plt
        # import scipy.sparse as sp
        # R = sp.csc_matrix((valr,(Ir,Jr)), shape=(im*jm*nbeq,nbentry_now))
        # plt.figure()
        # plt.spy(R)
        # plt.show()
        Restrix = pet.createMatPetscCSR(Ir, Jr, valr, im*jm*nbeq, nbentry_now, 1)

    return Restrix


def __writestate_center_gh(filename, imloc, jmloc, w, xc, yc) :
    # print 'write file'
    f_out = open(filename , 'w')
    f_out.write('TITLE="state"\n')
    f_out.write('VARIABLES= "X" "Y" "ro" "rou" "rov" "row" "roe" \n')
    f_out.write('ZONE I = ' + str(imloc) + ',  J = ' + str(jmloc) + '\n')
    for j in range(jmloc):
        for i in range(imloc):
            ro  = w[i,j,0]
            rou = w[i,j,1]
            rov = w[i,j,2]
            row = w[i,j,3]
            roe = w[i,j,4]
            f_out.write(str(xc[i,j]) + ' ' + str(yc[i,j]) + ' ' +
                        str(ro)      + ' ' + str(rou)     + ' ' +
                        str(rov)     + ' ' + str(row)     + ' ' +
                        str(roe)     + '\n')
    f_out.close()

def __writeforcing_center(filename, imloc, jmloc, w, xc, yc) :
    # print 'write file'
    f_out = open(filename , 'w')
    f_out.write('TITLE="forcing"\n')
    f_out.write('VARIABLES= "X" "Y" "rou" "rov" "row" \n')
    f_out.write('ZONE I = ' + str(im) + ',  J = ' + str(jm) + '\n')
    for j in range(jmloc):
        for i in range(imloc):
            rou = w[i,j,0]
            rov = w[i,j,1]
            row = w[i,j,2]
            f_out.write(str(xc[i,j]) + ' ' + str(yc[i,j]) + ' ' +
                        str(rou)    + ' ' + str(rov)   + ' ' +
                        str(row)   +  '\n')
    f_out.close()


def __writearray(filename, array) :
    # print 'write file'
    # f_out = open(filename , 'w')
    f_out = open(filename , 'a')
    f_out.write('TITLE="eigenvalues"\n')
    for k in range(_np.shape(array)[0]):
        f_out.write(str(array[k])   +  '\n')
    f_out.close()

def __writearray2(filename, array, freq, wave) :
    # print 'write file'
    f_out = open(filename , 'a')
    # f_out.write('TITLE= "frequency" "wavenumber" "eigenvalues"\n')
    f_out.write(str(freq) + ' ')
    f_out.write(str(wave) + ' ')
    for k in range(_np.shape(array)[0]):
        # f_out.write(str(array[k]) + ' ')
        f_out.write(str(array[k][0]) + ' ')
    f_out.write('\n')
    f_out.close()


def read_PETSc(dir):

    ## Read Qq
    viewer=PETSc.Viewer().createBinary(dir+'Qq', PETSc.Viewer.Mode.READ)
    # viewer=PETSc.Viewer().createBinary(dir+'QqEc', PETSc.Viewer.Mode.READ)
    Qq=PETSc.Mat()
    Qq.create(PETSc.COMM_WORLD)
    Qq.setType('mpiaij')
    Qq.load(viewer)
    Qq.assemble()

    ## Read Qvol2
    viewer=PETSc.Viewer().createBinary(dir+'Qvol2', PETSc.Viewer.Mode.READ)
    Qvol2=PETSc.Mat()
    Qvol2.create(PETSc.COMM_WORLD)
    Qvol2.setType('mpiaij')
    Qvol2.load(viewer)
    Qvol2.assemble()

    ## Read Qvol2inv
    viewer=PETSc.Viewer().createBinary(dir+'Qvol2inv', PETSc.Viewer.Mode.READ)
    # viewer=PETSc.Viewer().createBinary(dir+'Qvol2', PETSc.Viewer.Mode.READ)
    Qvol2inv=PETSc.Mat()
    Qvol2inv.create(PETSc.COMM_WORLD)
    Qvol2inv.setType('mpiaij')
    Qvol2inv.load(viewer)
    Qvol2inv.assemble()

    ## Read P
    viewer=PETSc.Viewer().createBinary(dir+'P', PETSc.Viewer.Mode.READ)
    P=PETSc.Mat()
    P.create(PETSc.COMM_WORLD)
    P.setType('mpiaij')
    P.load(viewer)
    P.assemble()
    # P = pet.createMatIDPetsc(Qvol2.getSize()[0], Qvol2.getSize()[0])


    ## Read Jacsurvol
    viewer=PETSc.Viewer().createBinary(dir+'Jacsurvol', PETSc.Viewer.Mode.READ)
    Jacsurvol=PETSc.Mat()
    Jacsurvol.create(PETSc.COMM_WORLD)
    Jacsurvol.setType('mpiaij')
    Jacsurvol.load(viewer)
    Jacsurvol.assemble()

    return Qq, Qvol2, Qvol2inv, P, Jacsurvol

def computeandwrite_PETSc(dir, gam, mach, vol, w, im, jm, gh, nbentry, Jac, IA, JA, equations=[1, 2, 3]):

    # Qq = computeQ_Ec(w[gh:-gh,gh:-gh,:], vol[gh:-gh,gh:-gh])
    Qq = computeQ_Echu(w[gh:-gh,gh:-gh,:], vol[gh:-gh,gh:-gh], gam, mach)
    Qvol2, Qvol2inv = computeQ_L2(vol[gh:-gh,gh:-gh])
    P = computeP_everywhere(im, jm, equations)
    # P = pet.createMatIDPetsc(im*jm*5, im*jm*5)

    Jacvol = _np.zeros((nbentry), order='F')
    for k in range(nbentry):
        Jacvol[k] = Jac[k]/vol[(IA[k]//(jm*5))+gh, ((IA[k]%(jm*5))//5)+gh]
    Jacsurvol = pet.createMatPetscCSR(IA, JA, Jacvol, im*jm*5, im*jm*5, 5*(2*gh+1)**2)

    viewer = PETSc.Viewer().createBinary(dir+'Qq', 'w')
    viewer(Qq)
    viewer = PETSc.Viewer().createBinary(dir+'Qvol2', 'w')
    viewer(Qvol2)
    viewer = PETSc.Viewer().createBinary(dir+'Qvol2inv', 'w')
    viewer(Qvol2inv)
    viewer = PETSc.Viewer().createBinary(dir+'P', 'w')
    viewer(P)
    viewer = PETSc.Viewer().createBinary(dir+'Jacsurvol', 'w')
    viewer(Jacsurvol)


###################################################################################

if __name__ == '__main__':

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()


    treeBroadcast = str(sys.argv[1])
    out_dir       = str(sys.argv[2])
    freq          = float(sys.argv[3])
    wave          = float(sys.argv[4])

    os.system('mkdir -p %s' % out_dir)

    equations = [1, 2, 3]  #momentum
    # equations = [0, 1, 2, 3, 4]  #all equations

    frequency = _np.array([freq]) / (2.*_np.pi) / 1.e5
    wavenumber= _np.array([wave]) / 1.e5

    dic  = _np.load(treeBroadcast)
    gh   = dic['gh']
    x    = dic['xc'][gh:-gh,gh:-gh]
    y    = dic['yc'][gh:-gh,gh:-gh]
    im   = dic['im']
    jm   = dic['jm']
    vol  = dic['vol']
    w    = dic['FlowSolutionEndOfRun']
    gam  = dic['Gamma']
    mach = dic['Mach']
    IA     = dic['IA']
    JA     = dic['JA']
    Jacvol = dic['Aij']
    IAdz   = dic['IAdz']
    JAdz   = dic['JAdz']
    Jacdz  = dic['Aijdz']
    IAdz2  = dic['IAdz2']
    JAdz2  = dic['JAdz2']
    Jacdz2 = dic['Aijdz2']

    Qq = computeQ_Echu(w[gh:-gh,gh:-gh,:], vol[gh:-gh,gh:-gh], gam, mach)
    Qvol2, Qvol2inv = computeQ_L2(vol[gh:-gh,gh:-gh])
    P = computeP_everywhere(im, jm, equations)

    Jacsurvol = pet.createMatPetscCSR(IA, JA, Jacvol, im*jm*5, im*jm*5, 5*(2*gh+1)**2)
    Dz        = pet.createMatPetscCSR(IAdz, JAdz, Jacdz, im*jm*5, im*jm*5, 5*(2*gh+1)**2)
    Dzz       = pet.createMatPetscCSR(IAdz2, JAdz2, Jacdz2, im*jm*5, im*jm*5, 5*(2*gh+1)**2)

    xmin = x[0,0]
    # xmin = 1.4e5

    xmax = x[-1,0]
    xmax = 1.75e6

    ymin = y[0,0]

    ymax = y[0,-1]
    ymax = y[0,-1]/2


    # import computeBLthickness as compBL
    # Xplot, BL_thick, BL_disp_thick, BL_mom_thick, H12, inflec_point, inflec_point2 = compBL.computeBLquant(out_dir + file + '.dat')
    # DeltaOpt = 11000.
    # # DeltaOpt = 1.
    # indmax = _np.searchsorted(BL_disp_thick, DeltaOpt)
    # xmax = x[indmax,0]
    if rank==0: print(xmax, flush=True)

    restrixQ = restrix(im, jm, 5, x, y, xmin, xmax, ymin, ymax, square=True)
    Qq       = Qq.matMult(restrixQ)
    restrixP = restrix(im, jm, P.getSize()[1]//(im*jm), x, y, xmin, xmax, ymin, ymax, square=False)
    P        = P.matMult(restrixP)

    ##  Chu norm for response and L2 norm for forcing
    eigenvalue, eigenvector_forcing, eigenvector_response = resolvent(frequency, wavenumber, Jacsurvol, Qq, Qvol2, Qvol2inv, P, Dz, Dzz)
    ##  Chu norm for response and forcing
    # eigenvalue, eigenvector_forcing, eigenvector_response = resolvent(frequency, wavenumber, Jacsurvol, Qq, Qq,    Qvol2inv, P, Dz, Dzz)

    eig = _np.sqrt(_np.real(eigenvalue))
    if rank ==0: print(eig, flush=True)

    filename = out_dir + "/eigenval.dat"
    if rank ==0: __writearray2(filename, eig, freq, wave)

    if rank ==0:
        for k in range(len(eigenvalue)):
            # comm.Barrier()
            w_response = _np.reshape( _np.real(_np.array(eigenvector_response[k])), (im,jm,5))
            filename = out_dir + "/response_atcenter_eig_om{:.2}_be{:.2}_n{:d}_real.dat".format(freq, wave, k)
            __writestate_center_gh(filename, im, jm, w_response, x, y)
            # comm.Barrier()
            w_responsei = _np.reshape( _np.imag(_np.array(eigenvector_response[k])), (im,jm,5))
            filename = out_dir + "/response_atcenter_eig_om{:.2}_be{:.2}_n{:d}_imag.dat".format(freq, wave, k)
            __writestate_center_gh(filename, im, jm, w_responsei, x, y)
            # comm.Barrier()
            f_opt = _np.reshape( _np.real(_np.array(eigenvector_forcing[k])), (im,jm,5))
            filename = out_dir + "/forcing_atcenter_eig_om{:.2}_be{:.2}_n{:d}_real.dat".format(freq, wave, k)
            __writestate_center_gh(filename, im, jm, f_opt, x, y)
            # comm.Barrier()
            f_opti = _np.reshape( _np.imag(_np.array(eigenvector_forcing[k])), (im,jm,5))
            filename = out_dir + "/forcing_atcenter_eig_om{:.2}_be{:.2}_n{:d}_imag.dat".format(freq, wave, k)
            __writestate_center_gh(filename, im, jm, f_opti, x, y)
            
    comm.Barrier()



