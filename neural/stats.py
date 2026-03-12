import numpy as np
import ctypes
from math import tau
from numba import vectorize, njit
from numba.extending import get_cython_function_address

# Setup Erf
addr = get_cython_function_address("scipy.special.cython_special", "__pyx_fuse_1erf")
functype = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double)
erf_fn = functype(addr)

@vectorize(["float64(float64)"])
def vec_erf(x):
    return erf_fn(x)

@njit
def norm_pdf(x, mu, sigma):
    variance = sigma**2.0
    return np.exp((x - mu) ** 2.0 / (-2.0 * variance)) / np.sqrt(tau * variance)

@njit
def norm_cdf(x, mu, sigma):
    return 0.5 * (1.0 + vec_erf((x - mu) / (sigma * np.sqrt(2.0))))

@njit
def calc_dp_cdf_pdf(S, K, vol, T, r, q):
    # S, K, vol, T deben tener la misma forma (unidimensional)
    dp = (np.log(S / K) + (r - q + 0.5 * vol**2) * T) / (vol * np.sqrt(T))
    cdf_dp = norm_cdf(dp, 0.0, 1.0)
    pdf_dp = norm_pdf(dp, 0.0, 1.0)
    return dp, cdf_dp, pdf_dp

@njit
def calc_gamma_ex(S, vol, T, q, OI, pdf_dp):
    gamma = np.exp(-q * T) * pdf_dp / (S * vol * np.sqrt(T))
    return gamma * OI * S * S 

@njit
def calc_vanna_ex(S, vol, T, q, OI, dp, pdf_dp):
    dm = dp - vol * np.sqrt(T)
    vanna = -np.exp(-q * T) * pdf_dp * (dm / vol)
    return vanna * OI * S * vol

@njit
def calc_charm_ex(S, vol, T, r, q, opt_type, OI, dp, cdf_dp, pdf_dp):
    dm = dp - vol * np.sqrt(T)
    discount = np.exp(-q * T)
    part1 = (2.0 * (r - q) * T) - (dm * vol * np.sqrt(T))
    part2 = 2.0 * T * vol * np.sqrt(T)
    
    if opt_type == "call":
        charm = (q * discount * cdf_dp) - (discount * pdf_dp * (part1 / part2))
    else:
        charm = (-q * discount * (1.0 - cdf_dp)) - (discount * pdf_dp * (part1 / part2))
    return charm * OI * S * T

@njit
def calc_vega_ex(S, vol, T, q, OI, pdf_dp):
    vega = S * np.exp(-q * T) * np.sqrt(T) * pdf_dp
    return vega * OI

@njit
def calc_vomma_ex(vega_ex, dp, vol, T):
    d2 = dp - vol * np.sqrt(T)
    return vega_ex * (dp * d2) / vol

@njit
def calc_zomma_ex(gamma_ex, dp, vol, T):
    d2 = dp - vol * np.sqrt(T)
    return gamma_ex * (dp * d2 - 1.0) / vol
