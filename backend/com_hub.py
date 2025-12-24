# backend/com_hub.py
import asyncio
import json
import struct
import socket

class ComHub:
    """
    A lightweight communication hub that allows multiple LoLLMs workers 
    to synchronize events in real-time without database polling.
    Acts as a simple pub-sub server for the worker cluster.
    """
    def __init__(self, host='127.0.0.1', port=8042):
        self.host = host
        self.port = port
        self.clients = set()

    async def handle_client(self, reader, writer):
        self.clients.add(writer)
        addr = writer.get_extra_info('peername')
        try:
            while True:
                # Protocol: 4 bytes length (Big-Endian Unsigned Int) + JSON payload
                length_data = await reader.readexactly(4)
                if not length_data:
                    break
                length = struct.unpack('!I', length_data)[0]
                
                # Protect against oversized payloads (10MB limit)
                if length > 10 * 1024 * 1024:
                    print(f"Hub Warning: Rejecting oversized payload ({length} bytes) from {addr}")
                    break

                data = await reader.readexactly(length)
                if not data:
                    break
                
                # Broadcast the complete packet (length + data) to all OTHER connected workers
                packet = length_data + data
                
                for client in list(self.clients):
                    if client != writer:
                        try:
                            client.write(packet)
                            await client.drain()
                        except Exception:
                            self.clients.discard(client)
                            
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"Hub Error with client {addr}: {e}")
        finally:
            self.clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def run(self):
        try:
            server = await asyncio.start_server(self.handle_client, self.host, self.port)
            async with server:
                print(f"INFO: Communication Hub listening on {self.host}:{self.port}")
                await server.serve_forever()
        except Exception as e:
            print(f"CRITICAL: Failed to start Communication Hub: {e}")

def start_hub_server(host='127.0.0.1', port=8042):
    """Entry point for running the hub in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    hub = ComHub(host, port)
    loop.run_until_complete(hub.run())
