# Chapter 14: Comparison with Other Protocols

## Introduction

STT is one of many protocols for network communication. This chapter provides factual comparisons with common alternatives to help you understand when STT is the right choice and when other protocols may be more suitable.

**STT's Unique Position:** Agnostic binary transport with zero assumptions. Unlike HTTP (assumes documents/requests), WebRTC (assumes media), or BitTorrent (assumes files), STT works for ANY binary use case. YOU define semantics.

**Important:** STT is designed for the Seigr ecosystem with DHT-based peer discovery, content distribution, and NAT traversal capabilities built-in.

## STT vs HTTP/HTTPS

### HTTP/HTTPS Overview

HTTP (HyperText Transfer Protocol) is the protocol used for web browsing. HTTPS adds TLS encryption.

**Architecture**: Client-server  
**Model**: Request-response  
**Transport**: TCP  
**Encryption**: TLS (optional in HTTP, standard in HTTPS)

### Comparison

| Aspect | HTTP/HTTPS | STT |
|--------|------------|-----|
| **Model** | Client-server | Peer-to-peer |
| **Pattern** | Request-response | Bidirectional streaming |
| **Connection** | Can be stateless (HTTP/1) or persistent (HTTP/2) | Always stateful session |
| **Encryption** | TLS (standard crypto) | STC (probabilistic crypto) |
| **Browser Support** | Universal | None |
| **Latency** | Higher (request-wait-response) | Lower (continuous streaming) |
| **Overhead** | Text headers (HTTP/1) or binary (HTTP/2) | Binary frames |
| **Authentication** | Various (Basic, OAuth, etc.) | Pre-shared seed only |

### When to Use HTTP/HTTPS

- Web applications accessed through browsers
- RESTful APIs
- Simple request-response patterns
- Need universal client support
- One-way data flow (client requests, server responds)
- Content delivery (websites, APIs, downloads)

### When to Use STT

- Direct peer-to-peer communication
- Bidirectional streaming data
- No browser requirement
- STC cryptography is requirement
- Real-time continuous data flow
- Multiple simultaneous streams needed

### Example Use Cases

**HTTP/HTTPS:**

- Website: User requests page, server sends HTML
- API: App requests data, server sends JSON
- Download: Client requests file, server sends file

**STT:**

- Video call: Both peers send/receive video simultaneously
- File sync: Devices exchange file changes continuously
- Sensor network: Devices stream data to each other

## STT vs gRPC

### gRPC Overview

gRPC is a modern RPC (Remote Procedure Call) framework by Google.

**Architecture**: Client-server  
**Model**: RPC with streaming support  
**Transport**: HTTP/2  
**Serialization**: Protocol Buffers  
**Encryption**: TLS

### Comparison

| Aspect | gRPC | STT |
|--------|------|-----|
| **Model** | Client-server RPC | Peer-to-peer streaming |
| **Streaming** | Unary, server, client, bidirectional | Multiplexed streams |
| **Serialization** | Protocol Buffers | STT binary format |
| **Code Generation** | Required (protobuf compiler) | Not required |
| **Transport** | HTTP/2 over TCP | UDP or WebSocket |
| **Encryption** | TLS | STC |
| **Language Support** | Many languages | Python (currently) |

### When to Use gRPC

- Service-to-service communication in microservices
- Need strong typing and code generation
- Client-server model fits your architecture
- Want HTTP/2 benefits (multiplexing, header compression)
- Need broad language support

### When to Use STT

- Peer-to-peer applications
- STC cryptography requirement
- No need for code generation
- UDP transport preferred (lower latency)
- Custom binary protocol needed

## STT vs WebRTC

### WebRTC Overview

WebRTC (Web Real-Time Communication) enables peer-to-peer communication in browsers.

**Architecture**: Peer-to-peer (with signaling server)  
**Model**: Real-time media streaming  
**Transport**: UDP (with SRTP/DTLS)  
**Use Cases**: Video/audio calls, data channels

### Comparison

| Aspect | WebRTC | STT |
|--------|--------|-----|
| **Peer-to-Peer** | Yes (requires signaling server) | Yes (direct) |
| **Browser Support** | Excellent | None |
| **Media Focus** | Optimized for A/V | General binary data |
| **NAT Traversal** | Built-in (ICE/STUN/TURN) | Not yet implemented |
| **Encryption** | DTLS-SRTP | STC |
| **Setup Complexity** | Higher (signaling needed) | Lower (direct if IPs known) |
| **Data Channels** | Limited | Multiple streams native |

### When to Use WebRTC

- Browser-based applications
- Video/audio conferencing
- Need NAT traversal without manual config
- Standardized protocol important
- Interoperability with existing WebRTC clients

### When to Use STT

- Non-browser applications
- Binary data streaming (not just media)
- STC cryptography requirement
- Direct peer connections (IPs known)
- Custom protocol control needed

## STT vs QUIC

### QUIC Overview

QUIC is a modern transport protocol by Google, now standardized as HTTP/3's transport.

**Architecture**: Client-server or peer-to-peer  
**Model**: Stream-multiplexed  
**Transport**: UDP-based  
**Encryption**: TLS 1.3 integrated

### Comparison

| Aspect | QUIC | STT |
|--------|------|-----|
| **Transport** | UDP | UDP or WebSocket |
| **Streams** | Multiplexed | Multiplexed |
| **0-RTT** | Supported | Not supported |
| **Encryption** | TLS 1.3 | STC |
| **Connection Migration** | Supported | Not supported |
| **Standardization** | IETF standard | Not standardized |
| **Adoption** | Growing (HTTP/3) | Limited |

### When to Use QUIC

- Need fast connection establishment (0-RTT)
- Connection migration important (mobile)
- Want IETF standardization
- HTTP/3 benefits needed
- Standard TLS encryption sufficient

### When to Use STT

- STC cryptography required
- Simpler implementation preferred
- Custom protocol requirements
- No need for connection migration
- Not using HTTP

## STT vs Raw TCP/UDP

### Raw Sockets Overview

Direct use of TCP or UDP sockets without application protocol.

### Comparison

| Aspect | Raw TCP/UDP | STT |
|--------|-------------|-----|
| **Abstraction** | Low-level | High-level |
| **Encryption** | None (you implement) | Built-in (STC) |
| **Framing** | You implement | Built-in |
| **Sessions** | You implement | Built-in |
| **Streams** | You implement | Built-in |
| **Complexity** | High (DIY everything) | Lower (protocol provided) |

### When to Use Raw Sockets

- Need absolute control over protocol
- Implementing a new custom protocol
- Performance critical (no abstraction overhead)
- Very specific requirements

### When to Use STT

- Need encryption without implementing crypto
- Want session/stream management handled
- Binary protocol with framing needed
- Focus on application logic, not protocol

## STT vs BitTorrent

### BitTorrent Overview

BitTorrent is a peer-to-peer file-sharing protocol.

**Architecture**: Peer-to-peer swarm  
**Model**: Distributed file sharing  
**Focus**: Efficient file distribution

### Comparison

| Aspect | BitTorrent | STT |
|--------|------------|-----|
| **Model** | Many-to-many (swarm) | One-to-one and many-to-many (DHT + server mode) |
| **Purpose** | File distribution | General binary streaming + content distribution |
| **Chunking** | File pieces | Frame-based and content chunks |
| **Redundancy** | High (many sources) | Content-addressed DHT with multi-peer support |
| **Encryption** | Optional | Always (STC) |

### When to Use BitTorrent

- Distributing large files to many users **right now**
- Mature ecosystem with existing trackers/DHT
- File sharing is primary use case
- Standard tooling widely available

### When to Use STT

- Seigr ecosystem applications (designed for this)
- STC encryption required (content-addressed)
- Real-time streaming AND content distribution
- DHT-based content distribution with STC.hash
- Need unified protocol for sessions + distribution

## Decision Guide

### Choose HTTP/HTTPS When

- Building a web application or API
- Client-server model fits
- Need browser compatibility
- Simple request-response adequate

### Choose gRPC When

- Microservices architecture
- Need typed contracts (protobuf)
- Client-server RPC pattern
- Want HTTP/2 benefits

### Choose WebRTC When

- Browser-based peer-to-peer
- Real-time audio/video primary use case
- Need NAT traversal
- Standard protocol important

### Choose QUIC/HTTP/3 When

- Need fast connection setup
- Connection migration important
- Want latest HTTP benefits
- Standard TLS encryption sufficient

### Choose STT When

- **STC cryptography is required or preferred**
- Direct peer-to-peer communication
- Bidirectional streaming of binary data
- Multiple simultaneous streams needed
- No browser requirement
- Custom binary protocol acceptable
- Pre-shared seed distribution is feasible

## Limitations of STT

It's important to understand what STT does NOT provide:

### No Browser Support

STT is not a web protocol. Cannot be used directly in web browsers.

### Pre-Shared Seeds Required

No public-key infrastructure. Peers must exchange seeds out-of-band before connecting.

### No NAT Traversal (Yet)

STT includes STUN-like NAT type detection and hole punching coordination through the NATTraversal module.

### No Forward Secrecy

Compromise of shared seed allows decryption of all past and future sessions. Key rotation provides limited protection.

### Limited Language Support

Currently Python only. Other language implementations needed for broader adoption.

### Not Standardized

STT is not an IETF standard. Protocol changes are possible between versions.

## Performance Characteristics

### Latency

- **STT**: Low (UDP option, binary protocol)
- **HTTP/1.1**: Medium (TCP, text headers)
- **HTTP/2**: Low-Medium (TCP, binary, multiplexing)
- **WebRTC**: Very Low (UDP, optimized for real-time)
- **QUIC**: Low (UDP, 0-RTT option)

### Throughput

- **STT**: High (binary, efficient framing)
- **HTTP/1.1**: Medium (text overhead)
- **HTTP/2**: High (binary, compression)
- **WebRTC**: High (UDP, media-optimized)
- **QUIC**: High (UDP, stream multiplexing)

### Handshake Time

- **STT**: ~400ms (2 RTT over internet)
- **TLS 1.3**: ~200ms (1 RTT)
- **TLS 1.2**: ~400ms (2 RTT)
- **QUIC 0-RTT**: 0ms (with prior connection)

## Summary

STT is best suited for:

- Applications requiring STC cryptography
- Direct peer-to-peer binary streaming
- Multiple simultaneous data streams
- Non-browser environments
- Cases where pre-shared seed distribution is acceptable

STT is NOT suitable for:

- Web browsers (use WebRTC or WebSocket)
- Public web APIs (use HTTP/HTTPS)
- Wide deployment without seed management
- Cases requiring public-key authentication
- Need for IETF standardization

Choose the protocol that best fits your requirements. STT's unique value is STC integration for peer-to-peer streaming with pre-shared trust.

## Next Chapter

Continue to [Chapter 15: Design Decisions and Trade-offs](15_design_decisions.md) to understand why STT was designed the way it is.

---

**Review Questions:**

1. What is the main architectural difference between HTTP and STT?
2. Which protocol is best for browser-based video calls?
3. What is STT's main limitation compared to WebRTC?
4. When would you choose gRPC over STT?
5. What does STT offer that raw TCP/UDP doesn't?
