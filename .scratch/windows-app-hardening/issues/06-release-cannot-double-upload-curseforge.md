# 06: A release can't upload to CurseForge twice

**What to build:** A version bump on main publishes the addon to CurseForge and the GitHub release (addon zip + BragSetup.exe) as one all-or-nothing step, so a failure partway never leaves CurseForge with a version that has no tag.

Today the release job uploads to CurseForge before it fetches the Windows installer built by the earlier job. If fetching the installer or creating the GitHub release then fails, no tag is created, and the next push to main uploads the same version to CurseForge again.

After this ticket:
- Everything that can fail without side effects (packaging the zip, fetching BragSetup.exe, building the CurseForge metadata) happens before the CurseForge upload.
- A failed Windows build blocks the whole release, CurseForge included (decided: all or nothing). The workflow's header comment says so.
- Re-running a failed release (Actions → Run workflow) after fixing the cause still works and doesn't double-upload.

Source: Spec axis of the code review, finding (c)4.

**Blocked by:** 05 (Starting at login stays in the tray)

**Status:** done

- [x] The installer is downloaded, and the upload metadata built, before the CurseForge upload step
- [x] If the Windows job fails, neither CurseForge nor GitHub gets a release, and the workflow output says why
- [x] The workflow's header comment describes the all-or-nothing behaviour
- [x] The workflow still parses, and a push that doesn't bump the version only runs the test and Windows build jobs
