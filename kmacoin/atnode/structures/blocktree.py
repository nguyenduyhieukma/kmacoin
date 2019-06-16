from kmacoin.globaldef.hash import HASH_OF_NULL

from typing import List, Dict, Iterator


class BlockBranch(object):
    """
    A branch of blocks.

    Attributes:
        parent: the branch's parent.
        branch_index: the branch's index in its parent's list of sub-branches.
        root_block_index: the root block's index in the parent branch.
        block_ids: list of block IDs belonging to the branch.
        sub_branches: the branch's sub-branches.

    """
    def __init__(self, first_block_id: bytes, parent: 'BlockBranch' = None,
                 branch_index: int = None, root_block_index: int = None, ):
        self.parent = parent
        self.branch_index = branch_index
        self.root_block_index = root_block_index
        self.block_ids: List[bytes] = [first_block_id]
        self.sub_branches: List[BlockBranch] = []

    def add(self, block_id: bytes, prev_block_addr: List[int]) \
            -> Dict[bytes, List[int]]:
        """
        Add a block to the branch or one of its sub-branches.

        If a sub-branch's length is bigger than the main branch after the block
        is added, it will takeover and become new main branch.

        Args:
            block_id: the block ID to be added.
            prev_block_addr: the address of the block extended by the added
                block.

        Returns:
            Addresses of blocks whose positions have been changed.

        """
        if len(prev_block_addr) == 1:
            block_index = prev_block_addr[0]
            if block_index == len(self.block_ids) - 1:
                self.block_ids.append(block_id)
                return {block_id: [block_index + 1]}
            else:
                new_branch = BlockBranch(
                    block_id,
                    parent=self,
                    root_block_index=block_index,
                    branch_index=len(self.sub_branches)
                )
                self.sub_branches.append(new_branch)
                return {block_id: [new_branch.branch_index, 0]}
        else:
            branch_index, next_addr = prev_block_addr[0], prev_block_addr[1:]
            sub_branch = self.sub_branches[branch_index]
            result = sub_branch.add(block_id, next_addr)
            for k, v in result.items():
                result[k] = [branch_index] + v

            if len(sub_branch.block_ids) <= \
                    len(self.block_ids) - sub_branch.root_block_index - 1:
                return result
            else:
                return {**result, **self.swap(branch_index)}

    def get_path(self, block_addr: List[int]) -> Iterator[bytes]:
        """Get all the block IDs on the path to a specific block,
        given its address."""
        if len(block_addr) == 1:
            index = block_addr[0]
            for i in range(index + 1):
                yield self.block_ids[i]
        else:
            index, next_addr = block_addr[0], block_addr[1:]
            sub_branch = self.sub_branches[index]
            for i in range(sub_branch.root_block_index + 1):
                yield self.block_ids[i]

            yield from sub_branch.get_path(next_addr)

    def swap(self, index: int) -> Dict[bytes, List[int]]:
        """
        Swap the main branch with a sub-branch.

        Args:
            index: index of the sub-branch.

        Returns:
            Addresses of blocks whose positions have been changed.

        """
        sub_branch = self.sub_branches[index]
        tmp = sub_branch.block_ids
        sub_branch.block_ids = self.block_ids[sub_branch.root_block_index + 1:]
        self.block_ids = self.block_ids[:sub_branch.root_block_index + 1] + tmp

        result = {}
        for i in range(len(sub_branch.block_ids)):
            result[sub_branch.block_ids[i]] = [index, i]
        for i in range(sub_branch.root_block_index + 1, len(self.block_ids)):
            result[self.block_ids[i]] = [i]
        return result

    def traverse(self) -> Iterator[bytes]:
        """Traverse all the blocks in the branch and its sub-branches."""
        for block_id in self.block_ids:
            yield block_id
        for sub_branch in self.sub_branches:
            yield from sub_branch.traverse()


class BlockTree(object):
    """
    A tree of blocks.

    Attributes:
        main_branch: the tree's body.
        addresses: block ID -> address. address of the form: [index of block ID
            in main branch], or [index of sub-branch] + address of block ID in
            sub-branch.

    """
    def __init__(self):
        self.main_branch = BlockBranch(HASH_OF_NULL)
        self.addresses: Dict[bytes, List[int]] = {HASH_OF_NULL: [0]}

    def add(self, block_id: bytes, prev_id: bytes):
        """Add a block, given its block ID and `prev_id`."""
        self.addresses = {**self.addresses, **self.main_branch.add(
            block_id, self.addresses[prev_id])}

    def get_height(self) -> int:
        """Return the height of this tree. The root block doesn't count."""
        return len(self.main_branch.block_ids) - 1

    def get_top_block(self) -> bytes:
        """Return the ID of the top block of this tree."""
        return self.main_branch.block_ids[-1]

    def has_block(self, block_id: bytes) -> bool:
        """Test for block membership."""
        return block_id in self.addresses

    def get_path(self, block_id: bytes) -> Iterator[bytes]:
        """Get all the block IDs on the path to a specific block."""
        return self.main_branch.get_path(self.addresses[block_id])

    def traverse(self) -> Iterator[bytes]:
        """Traverse all the blocks in the tree."""
        yield from self.main_branch.traverse()
