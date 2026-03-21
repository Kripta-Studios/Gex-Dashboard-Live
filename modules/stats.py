import numpy as np
import ctypes
from math import tau
from numba import vectorize, njit
from numba.types import float64, UniTuple, string
from numba.extending import get_cython_function_address

addr = get_cython_function_address("scipy.special.cython_special", "__pyx_fuse_1erf")
functype = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_double)
erf_fn = functype(addr)


@vectorize([float64(float64)])
def vec_erf(x):
    return erf_fn(x)


@njit(float64[:, :](float64[:, :]))
def erf_njit(x):
    return vec_erf(x)


# Probability density function for a normal distribution
@njit(float64[:, :](float64[:, :], float64, float64))
def norm_pdf(x, mu, sigma):
    variance = sigma**2.0
    return np.exp((x - mu) ** 2.0 / (-2.0 * variance)) / np.sqrt(tau * variance)


# Cumulative distribution function for a normal distribution
@njit(float64[:, :](float64[:, :], float64, float64))
def norm_cdf(x, mu, sigma):
    return 0.5 * (1.0 + erf_njit((x - mu) / (sigma * np.sqrt(2.0))))


# S is spot price, K is strike price, vol is implied volatility
# T is time to expiration, r is risk-free rate, q is dividend yield
@njit(
    UniTuple(float64[:, :], 3)(
        float64[:, :], float64[:], float64[:], float64[:], float64, float64
    )
)
def calc_dp_cdf_pdf(S, K, vol, T, r, q):
    dp = (np.log(S / K) + (r - q + 0.5 * vol**2) * T) / (vol * np.sqrt(T))
    cdf_dp = norm_cdf(dp, 0.0, 1.0)
    pdf_dp = norm_pdf(dp, 0.0, 1.0)
    return dp, cdf_dp, pdf_dp


# Black-Scholes Pricing Formula


@njit(
    float64[:, :](float64[:, :], float64[:], float64, string, float64[:], float64[:, :])
)
def calc_delta_ex(S, T, q, opt_type, OI, cdf_dp):
    if opt_type == "call":
        delta = np.exp(-q * T) * cdf_dp
    else:
        delta = -np.exp(-q * T) * (1 - cdf_dp)
    # change in option price per one percent move in underlying
    return delta * OI * S


@njit(
    float64[:, :](
        float64[:, :], float64[:], float64[:], float64, float64[:], float64[:, :]
    )
)
def calc_gamma_ex(S, vol, T, q, OI, pdf_dp):
    gamma = np.exp(-q * T) * pdf_dp / (S * vol * np.sqrt(T))
    # change in delta per one percent move in underlying
    return gamma * OI * S * S  # Gamma is same formula for calls and puts


@njit(
    float64[:, :](
        float64[:, :],
        float64[:],
        float64[:],
        float64,
        float64[:],
        float64[:, :],
        float64[:, :],
    )
)
def calc_vanna_ex(S, vol, T, q, OI, dp, pdf_dp):
    dm = dp - vol * np.sqrt(T)
    vanna = -np.exp(-q * T) * pdf_dp * (dm / vol)
    # change in delta per one percent move in IV
    # or change in vega per one percent move in underlying
    return vanna * OI * S * vol  # Vanna is same formula for calls and puts


@njit(
    float64[:, :](
        float64[:, :],
        float64[:],
        float64[:],
        float64,
        float64,
        string,
        float64[:],
        float64[:, :],
        float64[:, :],
        float64[:, :],
    )
)
def calc_charm_ex(S, vol, T, r, q, opt_type, OI, dp, cdf_dp, pdf_dp):
    dm = dp - vol * np.sqrt(T)
    if opt_type == "call":
        charm = (q * np.exp(-q * T) * cdf_dp) - np.exp(-q * T) * pdf_dp * (
            2 * (r - q) * T - dm * vol * np.sqrt(T)
        ) / (2 * T * vol * np.sqrt(T))
    else:
        charm = (-q * np.exp(-q * T) * (1 - cdf_dp)) - np.exp(-q * T) * pdf_dp * (
            2 * (r - q) * T - dm * vol * np.sqrt(T)
        ) / (2 * T * vol * np.sqrt(T))
    # change in delta per day until expiration
    return charm * OI * S * T


@njit(cache=True)
def calc_delta_adjusted_gex(gamma_ex, cdf_dp, T, q, opt_type):
    """
    Calcula el GEX ajustado por Delta (ponderado por la exposición real).
    Filtra la Gamma de opciones lejanas (OTM) y resalta las ATM/ITM.
    Formula: GEX_raw * |Delta_unitaria|
    """
    discount = np.exp(-q * T)
    # Recalculamos la Delta unitaria (0 a 1) usando los inputs pre-calculados
    if opt_type == "call":
        unit_delta = discount * cdf_dp
    else:
        # Delta Put = -e^-qT * (1 - N(d1))
        unit_delta = -discount * (1.0 - cdf_dp)

    # Multiplicamos la Gamma Exposure por el valor absoluto de la Delta
    # Si la delta es alta (ITM), el GEX se mantiene casi igual.
    # Si la delta es baja (OTM), el GEX se reduce drásticamente.
    return gamma_ex * np.abs(unit_delta)


@njit(cache=True)
def calc_zomma_ex(gamma_ex, dp, vol, T):
    """
    Calcula la "Zomma Exposure" (GEX ajustado por Volatilidad).
    Mide cuánto cambia el GEX ante un movimiento del 1% en la Volatilidad Implícita.

    Zomma = Gamma * ((d1 * d2 - 1) / sigma)
    Aprovechamos que ya tenemos gamma_ex calculado.
    """
    # d2 = d1 - vol * sqrt(T)
    d2 = dp - vol * np.sqrt(T)

    # Factor de ajuste Zomma: (d1*d2 - 1) / vol
    zomma_factor = (dp * d2 - 1.0) / vol

    # Retorna el cambio en GEX por 1 punto de cambio en Vol
    return gamma_ex * zomma_factor


@njit(
    float64[:, :](
        float64[:, :], float64[:], float64[:], float64, float64[:], float64[:, :]
    )
)
def calc_vega_ex(S, vol, T, q, OI, pdf_dp):
    """
    Calcula la "Vega Exposure" (sensibilidad al cambio en IV).
    Vega = S * e^(-q*T) * sqrt(T) * N'(d1)
    Vega es la misma fórmula para calls y puts.
    """
    vega = S * np.exp(-q * T) * np.sqrt(T) * pdf_dp
    return vega * OI  # Vega exposure weighted by open interest


@njit(cache=True)
def calc_vomma_ex(vega_ex, dp, vol, T):
    """
    Calcula la "Vomma Exposure" (sensibilidad de Vega al cambio en IV).
    Mide cuánto cambia la Vega ante un movimiento del 1% en la Volatilidad Implícita.

    Vomma = Vega * (d1 * d2) / sigma
    Aprovechamos que ya tenemos vega_ex calculado.
    
    Args:
        vega_ex: (N, M) array - Vega exposure matrix
        dp: (N, M) array - d1 values  
        vol: (M,) array - volatilities per option
        T: (M,) array - time to expiration per option
    
    Returns:
        (N, M) array - Vomma exposure matrix
    """
    n_prices = vega_ex.shape[0]
    n_options = vega_ex.shape[1]
    
    # Crear output array
    vomma_ex = np.zeros((n_prices, n_options), dtype=np.float64)
    
    # Calcular para cada opción (columna)
    for i in range(n_options):
        sqrt_T = np.sqrt(T[i])
        vol_i = vol[i]
        
        # d2 = d1 - vol * sqrt(T)
        d2_col = dp[:, i] - vol_i * sqrt_T
        
        # Factor de ajuste Vomma: (d1 * d2) / vol
        vomma_factor = (dp[:, i] * d2_col) / vol_i
        
        # Aplicar a vega_ex
        vomma_ex[:, i] = vega_ex[:, i] * vomma_factor
    
    return vomma_ex


@njit(cache=True)
def calc_speed_ex(gamma_ex, dp, vol, T, S):
    """
    Calcula la "Speed Exposure" (sensibilidad de Gamma al cambio en el precio).
    Speed = - (Gamma / S) * (1 + d1 / (sigma * sqrt(T)))
    Aprovechamos que ya tenemos gamma_ex calculado.
    
    Args:
        gamma_ex: (N, M) array - Gamma exposure matrix
        dp: (N, M) array - d1 values
        vol: (M,) array - volatilities per option
        T: (M,) array - time to expiration per option
        S: (N, 1) array - spot prices (levels)
    
    Returns:
        (N, M) array - Speed exposure matrix
    """
    n_prices = gamma_ex.shape[0]
    n_options = gamma_ex.shape[1]
    
    # Crear output array
    speed_ex = np.zeros((n_prices, n_options), dtype=np.float64)
    
    # Calcular para cada opción (columna)
    for i in range(n_options):
        sqrt_T = np.sqrt(T[i])
        vol_i = vol[i]
        
        # Factor de ajuste Speed: (1 + d1 / (vol * sqrt_T))
        # El signo negativo se aplica al final
        speed_factor = (1.0 + dp[:, i] / (vol_i * sqrt_T))
        
        # Aplicar a gamma_ex (gamma_ex ya incluye OI * S * S)
        # Speed = - (Gamma / S) * speed_factor
        # Como gamma_ex es Gamma * OI * S^2, entonces:
        # speed_ex = - (gamma_ex / S) * speed_factor
        speed_ex[:, i] = -(gamma_ex[:, i] / S[:, 0]) * speed_factor
    
    return speed_ex