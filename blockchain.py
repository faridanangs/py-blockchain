import sys
import hashlib
import json
import requests
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse

class Blockchain:
    difficulty_target = "0000"

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_encoded).hexdigest()

    def __init__(self):
        self.nodes = set()

        self.chain = []
        self.current_transactions = []
        genesis_hash = self.hash_block("genesis_block")
        self.append_block(
            hash_of_previous_block=genesis_hash,
            nonce=self.proof_of_work(0, genesis_hash, [])
        )

    def add_node(self, address):
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)
        print(parse_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]

            if block['hash_of_previous_block'] != self.hash_block(last_block):
                return False

            if not self.valid_proof(
                current_index,
                block['hash_of_previous_block'],
                block['transaction'],
                block['nonce']):
                return False

            last_block = block
            current_index += 1

        return True

    def synchronize_blocks(self):
        neighbors = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbors:
            try:
                response = requests.get(f'http://{node}/blockchain')
                if response.status_code == 200:
                    length = response.json()['length']
                    chain = response.json()['chain']
                    if length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
            except requests.RequestException as e:
                print(f"Error syncing with node {node}: {e}")

        if new_chain:
            self.chain = new_chain
            return True
        return False

    def proof_of_work(self, index, hash_of_previous_block, transaction):
        nonce = 0

        while self.valid_proof(
            index,
            hash_of_previous_block,
            transaction,
            nonce) is False:
            nonce += 1

        return nonce

    def valid_proof(self, index, hash_of_previous_block, transaction, nonce):
        content = f'{index}{hash_of_previous_block}{transaction}{nonce}'.encode()
        content_hash = hashlib.sha256(content).hexdigest()
        return content_hash[:len(self.difficulty_target)] == self.difficulty_target

    def append_block(self, hash_of_previous_block, nonce):
        block = {
            "index": len(self.chain),
            "timestamp": time(),
            "transaction": self.current_transactions,
            "nonce": nonce,
            "hash_of_previous_block": hash_of_previous_block
        }
        self.current_transactions = []
        self.chain.append(block)
        return block

    def add_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            "sender": sender,
            "recipient": recipient,
            "amount": amount
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', "")

blockchain = Blockchain()

@app.route('/blockchain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine_block():
    blockchain.add_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1
    )

    last_block_hash = blockchain.hash_block(blockchain.last_block)
    index = len(blockchain.chain)
    nonce = blockchain.proof_of_work(index, last_block_hash, blockchain.current_transactions)
    block = blockchain.append_block(last_block_hash, nonce)
    response = {
        'message': "block baru sudah telah di tambahkan",
        'index': block['index'],
        'hast_of_previous_block': block['hash_of_previous_block'],
        'nonce': block['nonce'],
        'transaction': block['transaction']
    }

    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required_fields = ['sender', 'amount', 'recipient']
    if not all(k in values for k in required_fields):
        return 'Missing values', 400

    index = blockchain.add_transaction(
        values['sender'],
        values['recipient'],
        values['amount']
    )

    response = {'message': f'Transaksi akan di tambah ke block {index}'}
    return jsonify(response), 200

@app.route('/nodes/add_nodes', methods=['POST'])
def add_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return 'No nodes provided', 400

    for node in nodes:
        blockchain.add_node(node)

    return jsonify({
        "message": "Added node to blockchain",
        "nodes": list(blockchain.nodes)
    })

@app.route('/nodes/sync', methods=['GET'])
def synchronize_nodes():
    updated = blockchain.synchronize_blocks()
    if updated:
        response = {
            "message": "blockchain terbaru sudah di ambil",
            "blockchain": blockchain.chain
        }
    else:
        response = {
            "message": "Blockchain mengambil data index terpanjang",
            "blockchain": blockchain.chain
        }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(sys.argv[1]))
