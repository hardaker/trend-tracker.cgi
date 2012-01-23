#!/usr/bin/perl

use IO::File;
use IO::Dir;
use strict;
use CGI;

my $runpath = $ENV{'SCRIPT_FILENAME'};
$runpath =~ s/(.*)\/(.*)/$1/;
if (length($runpath) == 0 || ! -d $runpath) {
    Error("Failed to determine initial startup path");
}

my $configfile = "tend-tracker.config";
my $configfullpath = "$runpath/$configfile";

# determine what we shoud be doing
my $cgi = CGI->new;
my $query_type = $cgi->param('type');

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
