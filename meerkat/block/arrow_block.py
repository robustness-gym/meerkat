from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Hashable, Mapping, Sequence, Tuple, Union

import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather
import torch

from meerkat.block.ref import BlockRef
from meerkat.columns.numpy_column import NumpyArrayColumn
from meerkat.columns.tensor_column import TensorColumn

from .abstract import AbstractBlock, BlockIndex


class ArrowBlock(AbstractBlock):
    @dataclass(eq=True, frozen=True)
    class Signature:
        nrows: int
        klass: type

    def __init__(self, data: pa.Table, *args, **kwargs):
        super(ArrowBlock, self).__init__(*args, **kwargs)
        self.data = data

    @property
    def signature(self) -> Hashable:
        return self.Signature(
            klass=ArrowBlock,
            # we don't
            nrows=len(self.data),
        )

    def _get_data(self, index: BlockIndex) -> pa.Array:
        return self.data[index]

    @classmethod
    def from_data(cls, data: pa.Array) -> Tuple[ArrowBlock, Mapping[str, BlockIndex]]:
        """[summary]

        Args:
            data (np.ndarray): [description]
            names (Sequence[str]): [description]

        Raises:
            ValueError: [description]

        Returns:
            Tuple[ArrowBlock, Mapping[str, BlockIndex]]: [description]
        """
        data = pa.Table.from_pydict({"col": data})
        block_index = "col"
        return cls(data), block_index

    @classmethod
    def _consolidate(
        cls,
        block_refs: Sequence[BlockRef],
    ) -> BlockRef:
        table = pa.Table.from_pydict(
            # need to ignore index when concatenating
            {
                name: ref.block.data[col._block_index]
                for ref in block_refs
                for name, col in ref.items()
            }
        )
        block = cls(table)

        # pull out the block columns from all the block_refs
        columns = {}
        for ref in block_refs:
            columns.update(ref)

        new_columns = {
            name: col._clone(data=block[name]) for name, col in columns.items()
        }
        return BlockRef(block=block, columns=new_columns)

    @staticmethod
    def _convert_index(index):
        if torch.is_tensor(index):
            # need to convert to numpy for boolean indexing
            return index.numpy()
        if isinstance(index, NumpyArrayColumn):
            return index.data
        if isinstance(index, TensorColumn):
            # need to convert to numpy for boolean indexing
            return index.data.numpy()
        if isinstance(index, pd.Series):
            # need to convert to numpy for boolean indexing
            return index.values
        from meerkat.columns.pandas_column import PandasSeriesColumn

        if isinstance(index, PandasSeriesColumn):
            return index.data.values
        return index

    def _get(
        self, index, block_ref: BlockRef, materialize: bool = True
    ) -> Union[BlockRef, dict]:
        index = self._convert_index(index)
        # TODO: check if they're trying to index more than just the row dimension
        data = self.data[index]
        if isinstance(index, int):
            # if indexing a single row, we do not return a block manager, just a dict
            return {
                name: data[col._block_index] for name, col in block_ref.columns.items()
            }
        block = self.__class__(data)

        columns = {
            name: col._clone(data=block[col._block_index])
            for name, col in block_ref.columns.items()
        }
        # note that the new block may share memory with the old block
        return BlockRef(block=block, columns=columns)

    def _write_data(self, path: str):
        feather.write_feather(self.data, os.path.join(path, "data.feather"))

    @staticmethod
    def _read_data(path: str):
        return feather.read_table(os.path.join(path, "data.feather"))