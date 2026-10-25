import httpx
import pytest

from finbo import graph


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_upload_puts_to_drive_path(monkeypatch):
    monkeypatch.delenv("MS_GRAPH_DRIVE", raising=False)
    seen = {}

    def handler(request):
        seen.update(
            method=request.method, url=str(request.url), auth=request.headers["authorization"]
        )
        return httpx.Response(201, json={"webUrl": "https://onedrive.live.com/x"})

    url = graph.upload("tok", b"xlsx-bytes", http=client(handler))
    assert url == "https://onedrive.live.com/x"
    assert seen["method"] == "PUT" and seen["auth"] == "Bearer tok"
    assert seen["url"] == (
        "https://graph.microsoft.com/v1.0/me/drive/root:/Finbo/Finbo%20plan.xlsx:/content"
    )


def test_sharepoint_drive_is_configurable(monkeypatch):
    monkeypatch.setenv("MS_GRAPH_DRIVE", "sites/contoso.sharepoint.com,abc,def/drive")
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"data")

    assert graph.download("tok", http=client(handler)) == b"data"
    assert "/sites/contoso.sharepoint.com,abc,def/drive/root:/" in seen["url"]


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "rejected the sign-in"), (404, "No Finbo workbook"), (500, "HTTP 500")],
)
def test_errors_are_explained(status, message):
    with pytest.raises(graph.GraphError, match=message):
        graph.download("tok", http=client(lambda r: httpx.Response(status)))
