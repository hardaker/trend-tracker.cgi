#!/usr/bin/perl

use IO::File;
use IO::Dir;
use strict;
use CGI;
use Data::Dumper;

our %config;

my $runpath = $ENV{'SCRIPT_FILENAME'};
$runpath =~ s/(.*)\/(.*)/$1/;
if (length($runpath) == 0 || ! -d $runpath) {
    Error("Failed to determine initial startup path");
}

my $configfile = "trend-tracker.config";
my $configfullpath = "$runpath/$configfile";

# determine what we shoud be doing
my $cgi = CGI->new;
my $query_type = $cgi->param('type');

read_config($configfile);

if ($query_type eq 'submit') {
    handle_submit();
} elsif ($query_type eq 'report') {
    handle_report();
} elsif ($query_type eq 'dump') {
    handle_dump();
} else {
    Error("Unknown input parameters");
}

#######################################################################
# data handling routines
#

# handle incoming data submissions
sub handle_submit {
    print_headers();
    my $key        = $config{'key'};
    my $parameters = config_array('parameters');
    my $extras     = config_array('extras');
    my $count      = $config{'startat'} || 0;
    my %data;

    # loop through all the possibilities collecting data
    while (1) {
	last if ($cgi->param($key . $count) eq '');
	$data{$key . $count} = $cgi->param($key . $count);
        foreach my $parameter (@$parameters) {
	    $data{$parameter . $count} = $cgi->param($parameter . $count);
	}
	$count++;
    }

    # add in the singular extras
    foreach my $parameter (@$extras) {
	$data{$parameter . $count} = $cgi->param($parameter . $count);
    }

    if ($config{'logaddress'}) {
	my $addr = $cgi->remote_addr();
	if (lc($config{'logaddress'}) eq "sha1") {
	    eval 'require Digest::SHA1';
	    $addr = Digest::SHA1::sha1_base64($addr);
	}
	$data{'remote_address'} = $addr;
    }
    
    # XXX: do something with the data...
    print "<pre>\n";
    print Dumper(\%data);
    print "</pre>\n";
}

sub handle_report {
    print_headers();
}

sub handle_dump {
    print_headers("text/xml");
}

#######################################################################
# general routines
#
sub read_config {
    my ($file) = @_;
    my $fh = new IO::File;
    if (! -f $file || !$fh->open($file)) {
	Error("failed to open the config file: $file");
    }

    while(<$fh>) {
	next if (/^\s*#/);
	next if (/^\s*$/);
	Error ("Illegal configuration directive: $_") if (! /:/);
	
	my ($key, $value) = /^\s*([^:]+):\s*(.*)/;
	$config{$key} = $value;
    }
}

# splits a config token into separate pieces; Default separation is by comma
sub config_array {
    my ($token, $separator) = @_;

    return []          if (!exists($config{$token}));
    $separator = ","   if (!defined($separator));

    my @results = split(/$separator\s*/, $config{$token});
    return \@results;
}

#######################################################################
# utility routines

# prints the starting http headers
my $have_done_headers = 0;
sub print_headers {
    return if ($have_done_headers);
    $have_done_headers = 1;

    my ($type) = @_;

    $type ||= "text/html";
    #
    # print http headers
    #
    print "Content-Type: $type\n\n";
}

sub Error {
    print STDERR @_,"\n";
    print_headers();
    print "<h1>Internal Error; please contact an administrator</h1>\n";
    exit 0;
}
