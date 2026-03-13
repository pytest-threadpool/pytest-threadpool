import pytest

from tests.markers import parallelizable

# Overrides parent's "children" with narrower "parameters" scope.
pytestmark = [parallelizable("parameters"), pytest.mark.parallel_only]
