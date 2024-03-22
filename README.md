# SUF

## Overview

### TL;DR
Are you interested by OpenROAD or the evolving domain of modern, open-source, rapid EDA tools for silicon design?
This project operates as an enhancement graft that augments OpenROAD's capabilities.
By cloning this repository, you will obtain both OpenROAD and a suite of Python tools adept at managing the process from input generation to generating detailed output plots in a parallel fashion.
For a swift overview after cloning and setting up, as detailed in the subsequent sections, a user can engage with the available commands/scripts as follows:
1. Clone the repository.
2. Install as per the instructions below.
3. `cd graft_road/` to browse its structure.
4. `ls -la` to examine the file organization.
5. `cd tools`
6. `./run_example` to generate HDL for various designs with different PDKs and initiate the OpenROAD flow concurrently.
7. `./plot_example` to reveal the plotting capabilities.

## Graphically Speaking
Overall, SUF framework is best represented with the following Figure
![SUF Overview](pictures/SUF.png)

## Organization Hierarchy

file hierachy with explanations


## Installation Instructions

The `graft_road` directory contains the necessary submodules for translation tools. To clone `graft_road` and its submodules, use the following commands:

```bash
git clone --recurse-submodules https://github.com/Bynaryman/SUF.git
cd SUF/graft_road/translation_tools
```
