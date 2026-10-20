# Memory forensics concepts used in this project

These project-focused notes paraphrase selected material in Michael Hale Ligh,
Andrew Case, Jamie Levy, and AAron Walters, *The Art of Memory Forensics* (2014),
Chapters 1-7 and 19-21. Page numbers below are printed page numbers, not PDF
viewer indices. The supplied edition describes older systems and Volatility
interfaces; its commands and offsets must not be copied unchanged into this VM.

| Chapter | Useful concept | Connection to this experiment |
| --- | --- | --- |
| 1: Systems Overview, pp. 3-26 | A process sees virtual addresses; the OS and hardware translate them to physical memory. | A pointer printed by GDB cannot be treated as a byte offset into `ubuntu.lime`. |
| 2: Data Structures, pp. 27-43 | Types, pointer sizes, alignment, and container relationships give raw bytes meaning. | The decoder uses measured C++ layouts to distinguish IValue slots, tensor metadata, and allocations. |
| 3: The Volatility Framework, pp. 45-67 | A framework supplies memory interpretation and reusable analysis components. | Linux plugins locate the process; the external plugin handles the application-specific objects. |
| 4: Memory Acquisition, pp. 69-114 | Acquisition quality and preservation determine the reliability of later analysis. | Preserve the capture, record hashes, and do not confuse successful target recovery with proof that every physical page was acquired. |
| 5: Windows Objects and Pool Allocations, pp. 117-148 | Object scanning requires structural validation and corroboration. | Finding plausible bytes is weaker than validating pointers, bounds, shapes, and reference matches. The Windows pool structures themselves are not Linux structures. |
| 6: Processes, Handles, and Tokens, pp. 149-187 | Process names alone do not establish identity; relate processes to resources and context. | Correlate the PID, executable mapping, GDB session, and captured model object. Windows handles/tokens are not the Linux API we parse. |
| 7: Process Memory Internals, pp. 189-218 | Mapping attributes help separate code, stack, heap, and other regions. | Wrappers were on the stack; pointed-to model/tensor objects were in anonymous memory. Windows VAD layouts must not be substituted for Linux VMAs. |
| 19: Linux Memory Acquisition, pp. 577-589 | LiME preserves physical-range metadata and needs a module built for the target kernel. | The 32-byte range header explains why the dump is not simply a flat array starting at physical address zero. |
| 20: Linux Operating System, pp. 591-610 | ELF, kernel data structures, and address translation underpin Linux analysis. | The matching kernel ISF supplies OS layouts; the PyTorch profile supplies separate application layouts. |
| 21: Processes and Process Memory, pp. 611-635 | `task_struct` connects process identity to memory management, mappings, and resources. | PsList identifies PID 3183, Maps describes its VMAs, and the process layer translates application pointers. |

## Interpreting the evidence

**An address is meaningful only in its context.** PID 3183's model address is
valid for the original capture. A new execution can place its model elsewhere.
ASLR and allocator behavior make reused addresses unreliable.

**A wrapper is not the numeric data.** The tensor wrapper leads to TensorImpl,
then StorageImpl and an allocation. Shape, dtype, strides, and storage offset
determine how the allocation is interpreted. For this contiguous float32 case,
the first element is at `allocation_base + 4 * storage_offset`.

**Hexadecimal words and bytes are different views.** The first recorded weight
has float32 encoding `0x3df5a08b`, approximately 0.119935118. On a little-endian
target those four bytes appear as `8b a0 f5 3d`. A plausible float alone does not
prove that the surrounding allocation is the right tensor.

**Mappings describe ranges, not ownership of every object.** A VMA's start/end,
permissions, and backing path help classify a pointer. Multiple model objects
can share one anonymous mapping. A mapping existing does not guarantee that
every page in it is present in a physical-memory capture; pages can be missing
or swapped out.

**Hashing preserves identity, not completeness.** A SHA-256 digest can detect a
changed capture or output file. It does not prove correct acquisition or correct
interpretation. The evidence here combines address checks, structural checks,
byte-level comparison, and replay on 6,000 test images.

**Old layouts require translation into current mechanisms.** Chapter 21 describes
older linked-list/red-black-tree VMA organization. Current Linux documents
[Maple Trees for VMA tracking](https://docs.kernel.org/core-api/maple_tree.html).
The book's x86 translation examples are not ARM64 page-table recipes. We use
the target's exact symbol information and the tested ARM64 framework branch.
[Volatility 3 symbol tables](https://volatility3.readthedocs.io/en/latest/symbol-tables.html)
also differ from the book's older profile workflow.

Source: [the supplied textbook PDF](https://www.dropbox.com/s/5lihw8p0z8ncq8x/The-Art-of-Memory-Forensics.pdf?dl=0),
especially pp. 27-43, 69-70, 114, 148, 187, 189-217, 580-583, and 611-635.
The book PDF is not redistributed in this repository.
