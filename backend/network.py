"""Explicit, opt-in private-LAN prototype policy. No public deployment support."""
from dataclasses import dataclass, field
import ipaddress
import secrets

LOOPBACK_HOSTS = ('localhost', '127.0.0.1', '[::1]')


@dataclass(frozen=True)
class NetworkPolicy:
    lan_ip: str | None = None
    access_key: str = field(default='', repr=False)

    def __post_init__(self):
        if self.lan_ip:
            address = ipaddress.ip_address(self.lan_ip)
            # RFC1918 only: reject public, unspecified, loopback and link-local.
            if address.version != 4 or not any(address in ipaddress.ip_network(net) for net in
                    ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
                raise ValueError('LAN mode requires a specific RFC1918 IPv4 address')
            if len(self.access_key) < 32 or not all(33 <= ord(char) <= 126 for char in self.access_key):
                raise ValueError('LAN mode requires an ASCII access key of at least 32 characters')

    @property
    def hosts(self):
        return list(LOOPBACK_HOSTS) + ([self.lan_ip] if self.lan_ip else [])


class ApiAccess:
    """Authenticate before parsing uploads. Keys never go in URLs or audit logs."""
    def __init__(self, app, policy):
        self.app, self.policy = app, policy

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['path'].startswith('/api/') and self.policy.lan_ip:
            if scope['method'] != 'OPTIONS' and scope['path'] != '/api/health':
                from starlette.responses import JSONResponse
                headers = dict(scope.get('headers', []))
                supplied = headers.get(b'x-visurex-key', b'')
                if not secrets.compare_digest(supplied, self.policy.access_key.encode('ascii')):
                    return await JSONResponse({'detail': 'A valid session access key is required'}, 401)(scope, receive, send)
        await self.app(scope, receive, send)
