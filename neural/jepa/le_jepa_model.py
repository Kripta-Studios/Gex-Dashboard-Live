import torch
import torch.nn as nn
import torch.nn.functional as F

def SIGReg(x: torch.Tensor, num_slices: int = 1024, integration_points: int = 17) -> torch.Tensor:
    """
    Sketched Isotropic Gaussian Regularization (SIGReg) using Epps-Pulley statistic.
    Enforces the embeddings `x` to follow an isotropic Gaussian distribution.
    Based on LeJEPA (Balestriero and LeCun, 2025).
    
    Args:
        x: (N, K) tensor of embeddings (Batch, Dim).
        num_slices: Number of random 1D projections (M).
        integration_points: Number of integration knots for the characteristic function.
    Returns:
        Scalar loss.
    """
    N, K = x.shape
    device = x.device
    
    # 1. Sample random directions on the unit hypersphere
    A = torch.randn(K, num_slices, device=device)
    A = A / A.norm(p=2, dim=0, keepdim=True)
    
    # 2. Integration points for the Characteristic Function (CF)
    t = torch.linspace(-5, 5, integration_points, device=device)
    
    # 3. Theoretical CF for N(0, 1) and Gaussian window
    exp_f = torch.exp(-0.5 * t**2)
    
    # 4. Empirical CF
    # x @ A gives (N, M) projections.
    # unsqueeze(2) * t gives (N, M, T)
    x_t = (x @ A).unsqueeze(2) * t
    # Compute empirical CF: mean over batch (N) -> (M, T)
    ecf = torch.cos(x_t).mean(dim=0) + 1j * torch.sin(x_t).mean(dim=0)
    
    # 5. Weighted L2 distance between Empirical CF and Theoretical CF
    # The absolute value squared of the complex difference:
    # |(a+ib) - c|^2 = (a-c)^2 + b^2
    ecf_real = ecf.real
    ecf_imag = ecf.imag
    err = (ecf_real - exp_f).square() + ecf_imag.square()
    err = err * exp_f # Weighted by Gaussian window
    
    # 6. Integrate over t (dimension 1) and average over slices (dimension 0)
    T_stat = torch.trapz(err, t, dim=1) * N
    
    return T_stat.mean()


class ResidualBlock(nn.Module):
    def __init__(self, dim: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim * 2),
            nn.BatchNorm1d(dim * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim * 2, dim),
            nn.BatchNorm1d(dim),
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        return x + self.dropout(self.net(x))


class LeWorldModel(nn.Module):
    def __init__(self, input_dim: int, latent_dim: int = 128, hidden_dim: int = 512, num_blocks: int = 2):
        super().__init__()
        
        # Encoder: Maps input features to latent z_t
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            *[ResidualBlock(hidden_dim) for _ in range(num_blocks)],
            nn.Linear(hidden_dim, latent_dim)
        )
        
        # Predictor: Maps z_t to \hat{z}_{t+k}
        self.predictor = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            *[ResidualBlock(hidden_dim) for _ in range(num_blocks)],
            nn.Linear(hidden_dim, latent_dim)
        )
        
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode observation to latent space."""
        return self.encoder(x)
        
    def predict(self, z: torch.Tensor) -> torch.Tensor:
        """Predict future latent state from current latent state."""
        return self.predictor(z)

    def forward(self, x_t: torch.Tensor, x_future: torch.Tensor):
        """
        Forward pass for training.
        Returns:
            z_t: Latent state at time t
            z_future: Latent state at time t+k
            z_pred: Predicted latent state at time t+k
        """
        z_t = self.encode(x_t)
        # Note: in LeWorldModel, the target is encoded by the SAME encoder without stop-gradients.
        z_future = self.encode(x_future)
        z_pred = self.predict(z_t)
        return z_t, z_future, z_pred
