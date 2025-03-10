"""
Produce stats from GFF3 format
"""

from __future__ import print_function

import os
import pandas as pd
import json
import re
from collections import defaultdict

from mirtop.gff.classgff import feature
from mirtop import version

import mirtop.libs.logger as mylog
logger = mylog.getLogger(__name__)


def stats(args):
    """
    From a list of GFF files produce general isomiRs stats.

    Args:
        *args (namedtupled)*: arguments parsed from command line with
            *mirtop.libs.parse.add_subparser_stats()*.

    Returns:
        *(stdout) or (out_file)*: GFF general stats.
    """
    v = version.__version__
    message_info = ("# mirtop stats version {v}").format(**locals())
    out = list()
    for fn in args.files:
        if not os.path.exists(fn):
            raise IOError("%s doesn't exist" % fn)
        logger.info("Reading: %s" % fn)
        out.append(_calc_stats(fn))
    df_final = pd.concat(out)
    _dump_log(df_final, version, os.path.join(args.out, "mirtop_stats.log"))
    outfn = os.path.join(args.out, "mirtop_stats.txt")
    if args.out != "tmp_mirtop":
        with open(outfn, 'w') as outh:
            print(message_info, file=outh)
            df_final.to_csv(outh)
        logger.info("Stats saved at %s" % outfn)
    else:
        print(message_info)
        print(df_final)


def _get_samples(fn):
    with open(fn) as inh:
        for line in inh:
            if line.startswith("## COLDATA"):
                return line.strip().split(": ")[1].strip().split(",")
    raise ValueError("%s doesn't contain COLDATA header." % fn)


def _calc_stats(fn):
    """
    Read files and parse into categories
    """
    samples = _get_samples(fn)
    lines = []
    seen = set()
    ok = re.compile('pass', re.IGNORECASE)
    with open(fn) as inh:
        for line in inh:
            if line.startswith("#"):
                continue
            gff = feature(line)
            cols = gff.columns
            attr = gff.attributes
            logger.debug("## STATS: attribute %s" % attr)
            if not ok.match(attr['Filter']):
                continue

            # Handle missing 'Variant' key
            variant_attr = attr.get('Variant', '')  # Default to 'NA' if missing

            if "-".join([attr['UID'], variant_attr, attr['Name']]) in seen:
                continue
            seen.add("-".join([attr['UID'], variant_attr, attr['Name']]))
            lines.extend(_classify(cols['type'], attr, samples))
    df = _summary(lines)
    return df


def _classify(srna_type, attr, samples):
    """
    Parse the line and return one
    line for each category and sample.
    """
    # iso_5p, iso_3p, iso_add ...
    # FILTER :: exact/isomiR_type
    lines = []
    counts = dict(zip(samples, attr['Expression'].split(",")))
    for s in counts:
        # Handle missing 'Variant' key
        variant_attr = attr.get('Variant', '')
        if int(counts[s]) > 0:
            lines.append([srna_type, s, counts[s]])
        if variant_attr.find("iso") == -1:
            continue
        for v in variant_attr.split(","):
            if int(counts[s]) > 0:
                lines.append([v.split(":")[0], s, counts[s]])
    return lines


def _add_missing(df):
    # ref_miRNA_mean
    category = "ref_miRNA_mean"
    if sum(df['category']==category) == 0:
        df2 = pd.DataFrame({'category': category, 'sample': df['sample'].iat[0], 'counts': 0}, index=[0])
        df = pd.concat([df, df2], ignore_index = True)
    
    category = "isomiR_sum"
    if sum(df['category']==category) == 0:
        df2 =  pd.DataFrame({'category': category, 'sample': df['sample'].iat[0], 'counts': 0}, index=[0])
        df = pd.concat([df, df2], ignore_index = True)
    
    return df

def _summary(lines):
    """
    Summarize long table according to thresholds
    """
    # summarize  > 0, > 5, >10, >50, >100 and bind rows
    labels = ["category", "sample", "counts"]
    df = pd.DataFrame.from_records(lines, columns=labels)
    df.counts = df.counts.astype(int)
    df_sum = df.groupby(['category', 'sample'], as_index=False).sum()
    df_sum['category'] = ["%s_sum" % r for r in df_sum['category']]
    df_sum = _add_missing(df_sum)
    df_count = df.groupby(['category', 'sample'], as_index=False).count()
    df_count['category'] = ["%s_count" % r for r in df_count['category']]
    df_count = _add_missing(df_count)
    df_mean = df.groupby(['category', 'sample'], as_index=False).mean()
    df_mean['category'] = ["%s_mean" % r for r in df_mean['category']]
    df_mean = _add_missing(df_mean)
    df = pd.concat([df_sum, df_count, df_mean])
    return df


def _dump_log(df, version, out_file):
    """Function to dump the table into a json log file."""
    json_dict = defaultdict(dict)
    for index, row in df.iterrows():
        json_dict[row['sample']][row['category']] = row['counts']
    log = {'meta': {'tool': 'mirtop',
                    'version': 'v%s' % version.__version__,
                    'homepage': version.__url__},
           'metrics': json_dict}
    logger.debug(log)
    if out_file:
        with open(out_file, 'w') as outh:
            json.dump(log, outh)
