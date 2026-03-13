import pytest

from tests.markers import parallelizable

pytestmark = [parallelizable("children"), pytest.mark.parallel_only]
