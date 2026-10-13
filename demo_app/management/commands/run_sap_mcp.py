from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Run the mock SAP MCP HTTP server (order/dispatch tools)'

    def handle(self, *args, **options):
        from sap_mcp.server import create_mcp

        host = getattr(settings, 'SAP_MCP_HOST', '127.0.0.1')
        port = getattr(settings, 'SAP_MCP_PORT', 3100)
        self.stdout.write(self.style.SUCCESS(
            f'Starting mock SAP MCP server at http://{host}:{port}/mcp'
        ))
        mcp = create_mcp()
        mcp.run(transport='streamable-http')
