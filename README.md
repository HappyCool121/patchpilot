# PatchPilot

Implementation of [spec V1.1](mvp.md): one Streamlit screen, one seeded discount
bug, one real Nosana repair request, and verification inside a fresh Daytona sandbox.
There is no database, API service, retry loop or simulated provider mode.

## Setup and launch

Requires Python 3.12+. From the checkout root:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e .
```

Set `DAYTONA_API_KEY` and `NOSANA_API_KEY` in your server environment. The Nosana key
needs `inference:use` permission and usable credits. See `.env.example` for optional
model and snapshot settings. Values are not loaded automatically from `.env`.
Never commit keys or enter them in a public UI.

```sh
.venv/bin/streamlit run patchpilot/ui.py --server.address 127.0.0.1
```

The app checks the Nosana model list and Daytona read-only API access when keys are
present. These checks do not prove a sandbox can run or inference credits are usable;
the run itself provides that evidence. Choose `NOSANA_MODEL` explicitly for a
rehearsed demo. Otherwise the first advertised model is tried; incompatible or
unavailable chat models surface as errors. Provider checks can be refreshed in the UI.

Press **Repair demo bug**. The original fixture is uploaded to a fresh sandbox,
pytest 8.3.5 is installed there, and `python -m pytest -q` captures the baseline.
Nosana receives bounded implementation, read-only tests and failing output.
Only one nonempty, exact-match replacement in `discount.py` is accepted. Tests
remain unchanged. The identical command reruns after application. Provider calls
and sandbox commands have finite timeouts; there is no automatic model retry.
Sandbox deletion is attempted on every exit path. Cleanup failures are displayed
separately with the sandbox ID for manual cleanup in Daytona.

The app preserves diagnosis, diff, model ID and request/response, command output,
exit codes and verdict in the latest Streamlit session run. Download evidence
before starting another run or closing the session. Keys stay on the server and
known configured values are redacted from displayed evidence. No secrets are
uploaded into the sandbox. Generated code never runs on the app host.

The fixture deliberately uses a wrong discount formula. Its read-only tests cover
normal, zero and full discounts. A new manual run always uploads the original
defect. `VERIFIED` requires baseline exit 1, an applied patch and rerun exit 0.
Still-failing tests produce `NOT VERIFIED`; a passing baseline stops without inference.
Other pytest exit codes, zero-test runs, provider failures and malformed edits are
errors. Passing the designated tests does not establish general correctness.

Network access is required to Daytona and `inference.nosana.com`, and from Daytona
to PyPI. TLS verification must remain enabled. For development, keep the app on
loopback; authenticate access before exposing a server that spends provider credits.

## Tests and implementation status

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Unit tests use explicitly labeled provider doubles for verdicts, patch constraints,
unchanged tests, cleanup, errors and the one-attempt limit. Adapter tests use HTTP
and SDK doubles; these do not establish live sponsor integration success.

The stable Daytona SDK is pinned and its interfaces checked against the installed
version. Live acceptance and the required recorded walkthrough need valid provider
credentials. No genuine end-to-end repair or video is claimed by the offline tests.
Before submission, run a real repair, check red baseline and green verification,
save the evidence, and record a credential-free 90–120-second walkthrough. Also
check non-fix, invalid edit, provider failure and already-passing baseline paths.
Product deployment and a landing page are deferred by the spec.
