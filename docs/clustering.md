# Clustering (Scale-Out Path)

This solution ships **single-node** by design — it covers small → large via
vertical sizing (see [sizing-and-tuning.md](sizing-and-tuning.md)). It is built
**quorum-ready**, so moving to a multi-node cluster later is non-destructive.

## Why single-node is the default

- Most workloads (even hundreds of millions of messages/day) run comfortably on one
  well-sized node.
- A cluster adds real operational cost: an odd node count, network partition
  handling, rolling-upgrade discipline, and shared quorum/Erlang-cookie config.
- Per [YAGNI], we don't ship cluster machinery until a workload needs broker-level
  HA. The pieces that make the upgrade smooth are already in place.

## What's already quorum-ready

- **Queues default to `x-queue-type=quorum`** (`RABBITMQ_DEFAULT_QUEUE_TYPE`,
  and the init container's default). Quorum queues are the Raft-based,
  cluster-native replacement for the removed classic mirrored queues.
- **Stable node identity** — `rabbit@${RABBITMQ_NODE_HOSTNAME}` keeps the data
  directory consistent across restarts.
- **Erlang cookie** is already a managed secret (`RABBITMQ_ERLANG_COOKIE`).
- **Policies/operator-policies** provisioning works cluster-wide unchanged.

## Upgrading to a 3-node cluster (outline)

A cluster needs an **odd** number of nodes (3 or 5) so quorum queues can elect a
leader and tolerate `(N-1)/2` node failures.

1. **Shared secrets** — every node uses the *same* `RABBITMQ_ERLANG_COOKIE`.
2. **Unique, resolvable node names** — `rabbit@node1`, `rabbit@node2`,
   `rabbit@node3`, each reachable on port 25672 (Erlang distribution).
3. **Peer discovery** — configure
   `cluster_formation.peer_discovery_backend` (classic config, DNS, or
   `rabbit_peer_discovery_*`) so nodes find each other on boot.
4. **Partition handling** — set `cluster_partition_handling = pause_minority`
   (recommended for quorum queues) so a minority partition stops serving rather
   than diverging.
5. **Quorum group size** — quorum queues replicate to all (or `x-quorum-initial-group-size`)
   members. With 3 nodes you tolerate 1 node down.
6. **Load balancing** — front AMQP (5672/5671) with a TCP load balancer; point
   clients at the VIP. The Management UI can stay behind Traefik/Coolify.

The init container, sizing knobs, TLS modes, and CI/CD all carry over unchanged —
only the compose topology and the few cluster-formation settings are new.

## References

- [Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues)
- [Clustering Guide](https://www.rabbitmq.com/docs/clustering)
- [Cluster Formation & Peer Discovery](https://www.rabbitmq.com/docs/cluster-formation)
- [Partitions](https://www.rabbitmq.com/docs/partitions)

[YAGNI]: https://martinfowler.com/bliki/Yagni.html
