"""MCP tools for the competitive landscape, driven offline."""

from livemeta.core.store import SnapshotStore
from livemeta.mcp import server
from tests.test_ci_ctgov import _study


class _PipelineClient:
    def __init__(self, studies):
        self._studies = studies

    def fetch_study(self, nct_id):
        return {}

    def search_studies(self, query, page_size=20):
        return []

    def search_pipeline(self, query, page_size=1000):
        return self._studies

    def search_by_sponsor(self, name, page_size=1000):
        return self._studies


class _StubOpenFda:
    def approvals_by_sponsor(self, sponsor, limit=50):
        from livemeta.core.ci.schema import RegulatoryApproval

        return [RegulatoryApproval(drug="Semaglutide", application_number="NDA1")]


def _setup(tmp_path, studies):
    server.set_client(_PipelineClient(studies))
    server.set_store(SnapshotStore(tmp_path))
    server.set_openfda(_StubOpenFda())


def test_map_landscape_tool_returns_matrix(tmp_path):
    _setup(
        tmp_path,
        [
            _study(nct="NCT1", interventions=(("DRUG", "Semaglutide"),)),
            _study(nct="NCT2", interventions=(("DRUG", "Tirzepatide"),)),
        ],
    )
    ls = server.map_landscape("Type 2 Diabetes")
    assert set(ls.assets) == {"Semaglutide", "Tirzepatide"}


def test_map_landscape_as_of_reconstructs_past(tmp_path):
    _setup(
        tmp_path,
        [_study(nct="NCT1", start="2015-03", interventions=(("DRUG", "Semaglutide"),))],
    )
    server.map_landscape("T2D")  # seed
    assert server.map_landscape("T2D", as_of="2010-01-01").cells == []


def test_track_asset_tool_returns_timeline(tmp_path):
    _setup(
        tmp_path,
        [_study(nct="NCT1", interventions=(("DRUG", "Semaglutide"),))],
    )
    events = server.track_asset("T2D", "Semaglutide")
    assert events and all(e.asset_name == "Semaglutide" for e in events)


def test_company_pipeline_tool_spans_indications_with_approvals(tmp_path):
    _setup(
        tmp_path,
        [
            _study(nct="NCT1", conditions=("Type 2 Diabetes",),
                   interventions=(("DRUG", "Semaglutide"),)),
            _study(nct="NCT2", conditions=("Obesity",),
                   interventions=(("DRUG", "Semaglutide"),)),
        ],
    )
    cp = server.company_pipeline("Novo Nordisk")
    assert cp.sponsor == "Novo Nordisk"
    assert set(cp.indications) == {"Type 2 Diabetes", "Obesity"}
    assert [a.application_number for a in cp.approvals] == ["NDA1"]
