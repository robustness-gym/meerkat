from itertools import product

import numpy as np
import pytest
import torch

import meerkat as mk
from meerkat.block.manager import BlockManager


def test_consolidate_no_op():
    mgr = BlockManager()
    col1 = mk.NumpyArrayColumn(data=np.arange(10))
    mgr.add_column(col1, "a")
    col2 = mk.NumpyArrayColumn(np.arange(10) * 2)
    mgr.add_column(col2, "b")
    col2 = mk.NumpyArrayColumn(np.arange(10, dtype=float) * 2)
    mgr.add_column(col2, "c")
    block_ref = mgr.get_block_ref("c")

    assert len(mgr._block_refs) == 3
    mgr.consolidate()
    assert len(mgr._block_refs) == 2

    # assert that the block_ref hasn't changed for the isolated block ref
    assert mgr.get_block_ref("c") is block_ref


def test_consolidate():
    mgr = BlockManager()

    col1 = mk.NumpyArrayColumn(data=np.arange(10))
    mgr.add_column(col1, "col1")
    col2 = mk.NumpyArrayColumn(np.arange(10) * 2)
    mgr.add_column(col2, "col2")
    col3 = mk.PandasSeriesColumn(np.arange(10) * 3)
    mgr.add_column(col3, "col3")
    col4 = mk.PandasSeriesColumn(np.arange(10) * 4)
    mgr.add_column(col4, "col4")
    col5 = mk.TensorColumn(torch.arange(10) * 5)
    mgr.add_column(col5, "col5")
    col6 = mk.TensorColumn(torch.arange(10) * 6)
    mgr.add_column(col6, "col6")

    assert len(mgr._block_refs) == 6
    mgr.consolidate()
    assert len(mgr._block_refs) == 3

    # check that the same object backs both the block and the column
    for name, col in [("col1", col1), ("col2", col2)]:
        assert mgr[name].data.base is mgr.get_block_ref(name).block.data
        assert (mgr[name] == col).all()

    # check that the same object backs both the block and the column
    for name, col in [("col3", col3), ("col4", col4)]:
        assert mgr[name].data is mgr.get_block_ref(name).block.data[name]
        assert (mgr[name] == col).all()

    # check that the same object backs both the bock
    for name, col in [("col5", col5), ("col6", col6)]:
        # TODO (sabri): Figure out a way to check this for tensors
        assert (mgr[name] == col).all()


def test_consolidate_multiple_types():
    mgr = BlockManager()

    for dtype in [int, float]:
        for idx in range(3):
            col = mk.NumpyArrayColumn(np.arange(10, dtype=dtype))
            mgr.add_column(col, f"col{idx}_{dtype}")
    mgr.add_column(mk.PandasSeriesColumn(np.arange(10) * 4), "col4_pandas")
    mgr.add_column(mk.PandasSeriesColumn(np.arange(10) * 5), "col5_pandas")

    assert len(mgr._block_refs) == 8
    mgr.consolidate()
    assert len(mgr._block_refs) == 3


@pytest.mark.parametrize(
    "num_blocks, consolidated",
    product([1, 2, 3], [True, False]),
)
def test_apply_get_multiple(num_blocks, consolidated):
    mgr = BlockManager()

    for dtype in [int, float]:
        for idx in range(num_blocks):
            col = mk.NumpyArrayColumn(np.arange(10, dtype=dtype) * idx)
            mgr.add_column(col, f"col{idx}_{dtype}")
    if consolidated:
        mgr.consolidate()

    for slc in [
        slice(2, 6, 1),
        slice(0, 1, 1),
        slice(2, 8, 3),
        np.array([1, 4, 6]),
        np.array([True, False] * 5),
    ]:
        new_mgr = mgr.apply(method_name="_get", index=slc)
        assert isinstance(new_mgr, BlockManager)
        for dtype in [int, float]:
            for idx in range(num_blocks):
                # check it's equivalent to applying the slice to each column in turn
                assert (
                    new_mgr[f"col{idx}_{dtype}"].data
                    == mgr[f"col{idx}_{dtype}"][slc].data
                ).all()

                # check that the base is the same (since we're just slicing)
                assert (
                    new_mgr[f"col{idx}_{dtype}"].data.base
                    is mgr[f"col{idx}_{dtype}"][slc].data.base
                ) == isinstance(slc, slice)


@pytest.mark.parametrize(
    "num_blocks, consolidated",
    product([1, 2, 3], [True, False]),
)
def test_apply_get_single(num_blocks, consolidated):
    mgr = BlockManager()

    for dtype in [int, float]:
        for idx in range(num_blocks):
            col = mk.NumpyArrayColumn(np.arange(10, dtype=dtype) * idx)
            mgr.add_column(col, f"col{idx}_{dtype}")
    if consolidated:
        mgr.consolidate()

    for slc in [0, 8]:
        result_dict = mgr.apply(method_name="_get", index=slc)
        isinstance(result_dict, dict)
        for dtype in [int, float]:
            for idx in range(num_blocks):
                # check it's equivalent to applying the slice to each column in turn
                assert result_dict[f"col{idx}_{dtype}"] == mgr[f"col{idx}_{dtype}"][slc]


def test_remove():
    mgr = BlockManager()
    col = mk.NumpyArrayColumn(np.arange(10))
    mgr.add_column(col, "a")
    col = mk.NumpyArrayColumn(np.arange(10))
    mgr.add_column(col, "b")

    assert len(mgr) == 2
    mgr.remove("a")
    assert len(mgr) == 1
    assert list(mgr.keys()) == ["b"]

    with pytest.raises(
        expected_exception=ValueError,
        match="Remove failed: no column 'c' in BlockManager.",
    ):
        mgr.remove("c")


def test_contains():
    mgr = BlockManager()
    col = mk.NumpyArrayColumn(np.arange(10))
    mgr.add_column(col, "a")
    col = mk.NumpyArrayColumn(np.arange(10))
    mgr.add_column(col, "b")

    assert "a" in mgr
    assert "b" in mgr
    assert "c" not in mgr


@pytest.mark.parametrize(
    "num_blocks, consolidated",
    product([1, 2, 3], [True, False]),
)
def test_len(num_blocks, consolidated):
    mgr = BlockManager()
    for dtype in [int, float]:
        for idx in range(num_blocks):
            col = mk.NumpyArrayColumn(np.arange(10, dtype=dtype) * idx)
            mgr.add_column(col, f"col{idx}_{dtype}")

    if consolidated:
        mgr.consolidate()

    assert len(mgr) == num_blocks * 2