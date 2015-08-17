# What is bizast?

## Summary

bizast allows you to associate a name with a web resource, like an ip address or a magnet url.  It serves a role similar to DNS, but unlike DNS it is distributed so registration with a central authority is not required.

## Unsummary

Bizast is a distributed resource location system, based on distributed hash tables.  It is similar to DNS, but it has a http-based interface and can store any small message (suggested: URIs or simple host-port pairs).  Published resources are verified and versioned, so newer versions can replace old versions at the same address.

The bizast node exposes a web page that allows you to install `web+bz://` as a protocol in your browser, so `web+bz://` links work when accessed.

I am excited to try this with Bittorrent Maelstrom.

# Installation

## Linux or OS X

Requires Python 2.

Run:
```
pip install git+https://github.com/Rendaw/kademlia.git@verifiably-unpredictable-ids
pip install git+https://github.com/Rendaw/bizast
```

To start bizast at startup, copy `bizast.service` to `~/.config/systemd/user/` and run
```
systemctl --user enable bizast.service
systemctl --user start bizast.service
```

Note: bizast.service may need tweaking.

## Windows

1. Download and install Python 2.7: <https://www.python.org/downloads/>.  Use defaults, and check the box to add python to your path.
2. Download and install the Microsoft Visual C Runtime: <http://www.microsoft.com/en-us/download/details.aspx?id=40784>.  Select the x86 version (not 64-bit or arm).
3. Copy and extract this precompiled PyNaCl egg to c:\Python27\Lib\site-packages: <https://mega.nz/#!CokxCToS!CXP91nXfrDIiseunMgNXjY5X3c62XkP1gP0_N3L4GCk>
3. Download and extract the source for kademlia: <https://github.com/Rendaw/kademlia/archive/verified-unpredictable-ids.zip>.  Suggested path: c:\work
4. Download and extract the source for bizast: <https://github.com/Rendaw/bizast/archive/master.zip>.  Suggested path: c:\work
5. Open powershell and run `pip install c:\work\kademlia c:\work\bizast-master`

You should be able to run `bizast_server` now.  If you get a prompt to allow network access, allow access.  You will have to restart `bizast_server` afterwards.

# Usage

## Start a node

Run

```
bizast
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

Try to open [web+bz://test:370dc4f518483ff681c9731fc04f320b9d7670fe0359147d0b1b28710f319f5c](web+bz://test:370dc4f518483ff681c9731fc04f320b9d7670fe0359147d0b1b28710f319f5c) in a browser.  It should redirect you to <https://github.com/Rendaw/bizast>.

## Create a key for publishing

Run

```
naclkeys gen mykey
```

(replace mykey with something else if desired).

Follow the instructions.  The key will be in `~/.local/share/naclkeys/keys` on Linux or `%HOME%\AppData\Local\zarbosoft\naclkeys\keys` on Windows.

The hex value dumped to the command line is the key's fingerprint and will be used in the next step.

## Publish something

Run

```
bizastpub the-great-unknown magnet:?xt=urn:sha1:YNCKHTQCWBTRNJIV4WNAE52SJUQCZO5C
bizastpub MyBlog http://www.example.com/blog
```

`the-great-unknown` and 'MyBlog` are names.  A name combined with a key fingerprint is an address, and is constant for a name-key pair.  The commands above will dump the final address to the command line so you can put it in a letter to a friend or write it on a sticky note or whatever.

If you enter the addresses returned above into your browser, you would be redirected to <magnet:?xt=urn:sha1:YNCKHTQCWBTRNJIV4WNAE52SJUQCZO5C> and <http://www.example.com/blog> respectively.
