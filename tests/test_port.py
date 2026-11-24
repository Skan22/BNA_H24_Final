"""Le contrat de port tient pour le port du kit — c'est le test à copier pour un adaptateur BNA."""
from engine.port_contract import verifier_port
from engine.ports import LocalKitPort


def test_le_port_du_kit_respecte_le_contrat():
    port = LocalKitPort("public")
    for did in list(port.dossiers)[:25]:
        verifier_port(port, did)
