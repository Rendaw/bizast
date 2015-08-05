# What is bizast?

Bizast is a distributed resource location system, based on distributed hash tables.  It is similar to DNS, but it has a http-based interface and can store any small message (suggested: URIs or simple host-port pairs).  Published resources are verified and versioned, so newer versions can replace old versions at the same address.

The bizast node exposes a web page that allows you to install `bz://` as a protocol in your browser, so `bz://` links work when accessed.

I am excited to try this with Bittorrent Maelstrom.

# Installation

Requires Python 2.

Run:
```
pip install git+https://github.com/Rendaw/kademlia.git@verified-unpredictable-ids
pip install git+https://github.com/Rendaw/bizast
```

To start bizast at startup, copy `bizast.service` to `~/.config/systemd/user/` and run
```
systemctl --user enable bizast.service
systemctl --user start bizast.service
```

Note: bizast.service may need tweaking.

# Usage

## Start a node

Run

```
bizast_server
```

This is basically what `bizast.service` does if you're running the systemd unit.

## Configure your browser

Run

```
firefox http://localhost:62341/setup
```

or

```
google-chrome-stable http://localhost:62341/setup
```

and press the button.

## Create a key for publishing

Run

```
naclkeys gen mykey
```

(replace mykey with something else if desired).

Follow the instructions.  The key will be in something like `~/.local/share/naclkeys/`.

Note the hex value dumped to the command line.

## Start a node that allows publishing with your key

Run

```
bizast_server -p HASH
```

where HASH is the hex value dumped in the previous step.  You can also open your key file in a text editor and copy the value under `fingerprint`.

## Publish something

Run

```
bizast_client myblog http://my-ip-address/blog
```

Note the value dumped to the command line.  

If this worked, you should be able to open `bz://KEY` in your browser (KEY is the value dumped to the command line in this step) and be redirected to http://my-ip-address/blog .
