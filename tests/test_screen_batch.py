"""Batch-API screening: the eligibility clinical read over the Messages Batch API.

Screening is the one pipeline stage whose cost scales with candidate count — one
model call per candidate. For a genuinely systematic, multi-source search that can
mean a thousand candidates, so the clinical read can run as a single Message
Batch at 50% of the per-token price instead of a thousand live calls. The
deterministic pre-filter, keyless degradation, reviewer overrides, and the
resulting decisions are identical to the serial path — only the transport differs.
"""

from types import SimpleNamespace

from livemeta.core.schema import PICO, Question
from livemeta.core.screen import _ScreenJudged, screen_candidates


def _question() -> Question:
    return Question(
        id="q",
        text="q",
        pico=PICO(
            population="adults with type 2 diabetes",
            intervention="GLP-1 receptor agonist",
            comparator="placebo",
            outcome="MACE",
        ),
    )


def _study(nct: str, study_type: str = "INTERVENTIONAL") -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": f"Trial {nct}"},
            "designModule": {"studyType": study_type},
        }
    }


def _epmc_doc(ref: str, title: str, abstract: str) -> dict:
    return {"id": ref, "source": "europepmc", "title": title, "abstract": abstract}


def _text_block(payload: _ScreenJudged) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=payload.model_dump_json())


class _BatchStub:
    """A minimal Messages Batch client: records the requests, returns canned,
    already-`ended` results keyed by the judgment supplied per custom_id."""

    def __init__(self, judgments: dict[str, _ScreenJudged]):
        self._judgments = judgments
        self.created_requests: list[dict] | None = None

    class _Batches:
        def __init__(self, outer):
            self._outer = outer

        def create(self, requests):
            self._outer.created_requests = list(requests)
            return SimpleNamespace(id="batch_1", processing_status="ended")

        def retrieve(self, _id):
            return SimpleNamespace(id="batch_1", processing_status="ended")

        def results(self, _id):
            for req in self._outer.created_requests:
                cid = req["custom_id"]
                judged = self._outer._judgments[cid]
                yield SimpleNamespace(
                    custom_id=cid,
                    result=SimpleNamespace(
                        type="succeeded",
                        message=SimpleNamespace(content=[_text_block(judged)]),
                    ),
                )

    class _Messages:
        def __init__(self, outer):
            self.batches = _BatchStub._Batches(outer)

    @property
    def messages(self):
        return _BatchStub._Messages(self)


def test_batch_screening_submits_one_request_per_clinical_read():
    judgments = {
        "NCT1": _ScreenJudged(eligible=True, reason="matches"),
        "NCT2": _ScreenJudged(
            eligible=False, domain="population", reason="children"
        ),
    }
    client = _BatchStub(judgments)
    studies = {"NCT1": _study("NCT1"), "NCT2": _study("NCT2")}

    decisions = screen_candidates(_question(), studies, llm_client=client, batch=True)

    # One batch request per candidate that needed the clinical read.
    assert client.created_requests is not None
    assert {r["custom_id"] for r in client.created_requests} == {"NCT1", "NCT2"}
    by_id = {d.study_id: d for d in decisions}
    assert by_id["NCT1"].decision == "included"
    assert by_id["NCT1"].by_claude is True
    assert by_id["NCT2"].decision == "excluded"
    assert by_id["NCT2"].domain == "population"


def test_batch_screening_preserves_candidate_order():
    q = _question().model_copy(update={"trial_ids": ["NCT2", "NCT1"]})
    judgments = {
        "NCT1": _ScreenJudged(eligible=True),
        "NCT2": _ScreenJudged(eligible=True),
    }
    studies = {"NCT1": _study("NCT1"), "NCT2": _study("NCT2")}

    decisions = screen_candidates(q, studies, llm_client=_BatchStub(judgments), batch=True)

    assert [d.study_id for d in decisions] == ["NCT2", "NCT1"]


def test_batch_still_excludes_on_the_deterministic_filter():
    # An observational trial is excluded on design alone and never enters the
    # batch — the model batch cannot rescue it.
    judgments = {"NCT1": _ScreenJudged(eligible=True)}
    client = _BatchStub(judgments)
    studies = {
        "NCT1": _study("NCT1"),  # interventional → batched
        "NCT2": _study("NCT2", study_type="OBSERVATIONAL"),  # excluded pre-batch
    }

    decisions = screen_candidates(_question(), studies, llm_client=client, batch=True)

    by_id = {d.study_id: d for d in decisions}
    assert by_id["NCT2"].decision == "excluded"
    assert by_id["NCT2"].domain == "design"
    assert {r["custom_id"] for r in client.created_requests} == {"NCT1"}


def test_batch_screens_a_europe_pmc_record_from_its_abstract():
    # A published (Europe PMC) candidate has no protocolSection; its screening
    # prompt must be built from the title + abstract, and it must still be batched.
    judged = _ScreenJudged(eligible=True, reason="CV outcomes trial in T2D adults")
    client = _BatchStub({"PMID:31234567": judged})
    studies = {
        "PMID:31234567": _epmc_doc(
            "PMID:31234567",
            "Semaglutide and cardiovascular outcomes",
            "Adults with type 2 diabetes; MACE was the primary endpoint.",
        )
    }

    decisions = screen_candidates(_question(), studies, llm_client=client, batch=True)

    assert decisions[0].decision == "included"
    assert decisions[0].by_claude is True
    prompt = client.created_requests[0]["params"]["messages"][0]["content"]
    assert "type 2 diabetes" in prompt  # abstract fed into the prompt


def test_batch_disabled_by_default_uses_serial_path():
    # Without batch=True, a client that only supports batches (no .parse) is not
    # used for a batch — the serial path handles it. Here we assert the serial
    # path is taken by giving a batch-only client and NOT opting in: it should
    # fall back to the keyless auto-include rather than raising.
    from types import SimpleNamespace as NS

    class _SerialOnly:
        @property
        def messages(self):
            # No `.parse`, no `.batches` — an unusable client for either path.
            return NS()

    studies = {"NCT1": _study("NCT1")}
    # batch not requested; client lacks .parse, so the serial read fails safely
    # to an auto-include (mirrors _claude_screen's except branch).
    decisions = screen_candidates(_question(), studies, llm_client=_SerialOnly())

    assert decisions[0].decision == "included"
