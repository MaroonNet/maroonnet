from spm.models.ring import RingModel
from spm.models.uniform import UniformModel

REGISTRY = {
    "uniform": UniformModel,
    "ring": RingModel,
    "ring_pooled": lambda: RingModel(pooled_only=True),
}
