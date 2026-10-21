# Windows candidate license review — 2026-10-03

The owner review already selected an open-source MIT project. Root now supplies
the standard [software license](../../LICENSE), using the collective RepoNPC
contributors notice and no invented personal copyright holder. The text follows
the [OSI MIT license](https://opensource.org/license/mit). This removes the
missing-file blocker; it does not grant rights to third-party artwork or weights.

The existing offline generator still follows the installed locked runtime graph,
collects package/native license files and pinned supplements, and includes the
font OFL. A pinned [source-availability notice](../../packaging/windows/licenses/SOURCE_AVAILABILITY.txt)
is now included in the generated third-party notices. The unmodified tqdm 4.70.0
source and its own MIT/MPL notices are available at the linked upstream tag.
[MPL section 3.2](https://www.mozilla.org/en-US/MPL/2.0/) requires recipients of
executable covered code to be told how to obtain its source. A different locked
tqdm version fails generation until the source locator is reviewed; tests cover
successful inclusion and preserving prior notices on that failure.

The frozen build copies root LICENSE and generated notices. Its SHA256SUMS cover
those delivered inputs. Installer and frozen receipts identify the exact binary
used, so a previous build is not promoted after source or notices change.

Public release still needs the final native/vendored inventory review, a clean
Windows walkthrough, and separate Man artwork provenance and visual approval.
The private Man draft is excluded from the production source and frozen bundle;
its local contact sheets/cards establish preparation only. Historical receipts
that reported a missing LICENSE remain immutable snapshots of that earlier run.
