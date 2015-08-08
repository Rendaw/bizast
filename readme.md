# What is bizast?

## Summary

bizast allows you to associate a name with a web resource, like an ip address or a magnet url.  It serves a role similar to DNS, but unlike DNS it is distributed so registration with a central authority is not required.

## Unsummary

Bizast is a distributed resource location system, based on distributed hash tables.  It is similar to DNS, but it has a http-based interface and can store any small message (suggested: URIs or simple host-port pairs).  Published resources are verified and versioned, so newer versions can replace old versions at the same address.

The bizast node exposes a web page that allows you to install `bz://` as a protocol in your browser, so `bz://` links work when accessed.

I am excited to try this with Bittorrent Maelstrom.

# Installation

## Linux or OS X

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

## Windows

1. Download and install Python 2.7: [https://www.python.org/downloads/].  Use defaults, and check the box to add python to your path.
2. Download and install the Microsoft Visual C Runtime: [http://www.microsoft.com/en-us/download/details.aspx?id=40784].  Select the x86 version (not 64-bit or arm).
3. Copy and extract this precompiled PyNaCl egg to c:\Python27\Lib\site-packages: [https://mega.nz/#!CokxCToS!CXP91nXfrDIiseunMgNXjY5X3c62XkP1gP0_N3L4GCk]
3. Download and extract the source for kademlia: [https://github.com/Rendaw/kademlia/archive/verified-unpredictable-ids.zip].  Suggested path: c:\work
4. Download and extract the source for bizast: [https://github.com/Rendaw/bizast/archive/master.zip].  Suggested path: c:\work
5. Open powershell and run `pip install c:\work\kademlia c:\work\bizast-master`

You should be able to run `bizast_server` now.  If you get a prompt to allow network access, allow access.  You will have to restart `bizast_server` afterwards.

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

Try to open [bz://test:370dc4f518483ff681c9731fc04f320b9d7670fe0359147d0b1b28710f319f5c] in a browser.  It should redirect you to [https://github.com/Rendaw/bizast].

## Create a key for publishing

Run

```
naclkeys gen mykey
```

(replace mykey with something else if desired).

Follow the instructions.  The key will be in `~/.local/share/naclkeys/keys` on Linux or `%HOME%\AppData\Local\zarbosoft\naclkeys\keys` on Windows.

The hex value dumped to the command line is the key's fingerprint and will be used in the next step.

## Start a node that allows publishing with your key

Run

```
bizast_server -p FINGERPRINT
```

where FINGERPRINT is the hex value dumped in the previous step.  You can also open your key file in a text editor and copy the value under `fingerprint` if you forgot the value from the previous step.

`-p FINGERPRINT` can be specified multiple times with different keys to whitelist different keys.

As long as this server is running it will republish any resources published with whitelisted keys periodically.

## Publish something

Run

```
bizast_client NAME http://my-ip-address/blog
```

The value dumped to the command line is the address you published, and is constant for a NAME-key pair.

If this worked, you should be able to open [bz://ADDRESS] in your browser (ADDRESS is the value dumped to the command line in this step) and be redirected to [http://my-ip-address/blog].
