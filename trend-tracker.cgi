#!/usr/bin/perl

use IO::File;
use IO::Dir;
use strict;
use CGI;
use Data::Dumper;
use DBI;

our %config;
our $dbh;

our $VERSION = '0.8';

my $runpath = $ENV{'SCRIPT_FILENAME'};
$runpath =~ s/(.*)\/(.*)/$1/;
if (length($runpath) == 0 || ! -d $runpath) {
    Error("Failed to determine initial startup path");
}

my $configfile = $ENV{'TREND_TRACKER_CONFIG'} || "trend-tracker.config";
my $configfullpath = "$runpath/$configfile";

# determine what we shoud be doing
my $cgi = CGI->new;
my $query_type = $cgi->param('type');

read_config($configfile);
init_db();

if ($query_type eq 'submit') {
    handle_submit();
} elsif ($query_type eq 'report') {
    handle_report();
} elsif ($query_type eq 'dump') {
    handle_dump();
} elsif ($config{'welcomenote'} && -f $config{'welcomenote'}) {
    print "Content-Type: text/html\n\n";
    open(I, $config{'welcomenote'});
    while(read(I, my $buffer, 4096) > 0) { print $buffer ; }
    close(I);
} else {
    Error("Unknown input parameters");
}

#######################################################################
# data handling routines
#

# handle incoming data submissions
sub handle_submit {
    print_headers();
    my $key         = $config{'key'};
    my $parameters  = config_array('parameters');
    my $extras      = config_array('extras');
    my $count       = $config{'startat'} || 0;
    my $legalvalues = $config{'values'};
    my $extravalues = $config{'extravalues'};
    my $keyvalues   = $config{'keyvalues'};

    my $cgitable    = $cgi->param('data');
    $cgitable      =~ s/[^a-zA-Z]//;
    # config always wins:
    my $table       = $config{'table'} || $cgitable || "data" ; 

    # create the insert statment and prepare it for use
    my $statement = "insert into $table (cgipid, timestamp, remoteaddress, $key, " . 
	join(", ", @$parameters) . ", " .
	join(", ", @$extras) .
	") values(" .
	("?, " x ($#$parameters + $#$extras + 5)) . "?)";

    my $sth = $dbh->prepare($statement);
    my $time = time();

    # loop through all the possibilities collecting data
    while (1) {
	last if ($cgi->param($key . $count) eq '');

	# store the key
	my $keyvalue = $cgi->param($key . $count);
	if ($keyvalue !~ /$keyvalues/i) {
	    Error("Illegal key value passed in");
	}

	my @values = ($$, $time);

	# calculate (maybe) the remote address and push it on
	if ($config{'logaddress'}) {
	    my $addr = $cgi->remote_addr();
	    if (lc($config{'logaddress'}) eq "sha1") {
		eval 'require Digest::SHA1';
		$addr = Digest::SHA1::sha1_hex($addr);
	    }
	    $addr;
	    push @values, $addr;
	} else {
	    push @values, ''; ## XXX: make this entirely optional in the future
	}

	push @values, $keyvalue;

        foreach my $parameter (@$parameters) {
	    my $val = $cgi->param($parameter . $count);
	    if ($val !~ /$legalvalues/i) {
		# if the value wasn't legal, then either we replace it with a 
		# blank or disallow the submission to continue.
		if (defined($config{'allowblanks'}) &&
		    ($config{'allowblanks'} eq '1' ||
		     $config{'allowblanks'} eq 'true')) {
		    $val = "";
		} else {
		    Error("Illegal value passed in for $parameter$count");
		}
	    }
	    push @values, $val;
	}

	foreach my $parameter (@$extras) {
	    my $val = $cgi->param($parameter);
	    if ($val !~ /$extravalues/i) {
		# if the value wasn't legal, then either we replace it with a 
		# blank or disallow the submission to continue.
		if (defined($config{'allowblanks'}) &&
		    ($config{'allowblanks'} ne '0' ||
		     $config{'allowblanks'} eq 'true')) {
		    $val = "";
		} else {
		    Error("Illegal value passed in for $parameter$count");
		}
	    }
	    push @values, $val;
	}

	$count++;
	$sth->execute(@values) unless ($cgi->param('__TESTONLY__'));
    }

    if ($config{'logaddress'}) {
	my $addr = $cgi->remote_addr();
	if (lc($config{'logaddress'}) eq "sha1") {
	    eval 'require Digest::SHA1';
	    $addr = Digest::SHA1::sha1_hex($addr);
	}
    }
    
    if ($config{'thankyounote'}) {
	print $config{'thankyounote'};
    } else {
	print "<h2>Thank you!</h2>\n";
    }

    if ($config{'thankyounotefile'}) {
	my $tnh = new IO::File;
	my $buffer;
	$tnh->open($config{'thankyounotefile'});
	while(read($tnh, $buffer, 4096) > 0) {
	    print $buffer;
	}
    }
}

sub init_db {
    $dbh = DBI->connect("$config{'database'}",
			$config{'dbuser'}, $config{'dbpassword'});
    if (!$dbh) {
	Error("Failed to connect to the database");
    }
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
#### WARNING: Must Match Copy in createdb
#             (to keep this file self-contained, we duplicate it here)
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
	if ($key eq 'include') {
	    read_config($value);
	} else {
	    $config{lc($key)} = $value;
	}
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

=pod

=head1 NAME

trend-tracker.cgi -- capture and analyize submitted data over time

=head1 SYNOPSIS

 Create a trend-tracker.config file using the example file

 # ./createdb -c trend-tracker.config

 Then copy the database, the .cgi script, and the config file into a
 web-accessible directory and point your application at it to
 start collecting data.

 Run the trend-analysis tool to analyize the data

=head1 SUBMITTING DATA

Data should be submitted to the script using standard http GET or POST
methods.  Included in the data should be the following keywords, in
addition to your own data:

=over

=item type

This value should be set to 'submit' in order to submit data to the database.

=item data

If you're supporting collecting data into multiple tables using a
single CGI script (not recommended), this can be used to select
between the different tables.

=item __TESTONLY__

This is a testing variable that should be set to a non-zero value if
the data shouln't actually be submitted to the database but everything
else should be done.

=back

=head1 EXAMPLE CONFIGURATION FILE

The following is an example configuration file that documents how the
system is intended to work.

  #
  # include: /etc/trend-tracker.config
  #      Allows you to include files elsewhere on the system.  This is
  #      actually the recommended way to store configuration, as it
  #      hides the rest of the configuration file outside the
  #      web-searchable areas.  Instead, put the rest of this file in something
  #      like /etc/trend-tracker.config and include that instead.
  include: /etc/trend-tracker.config
  #
  # database: DBI:SQLite:dbname=trend-tracker.sqlite3
  #      The perl DBI database handle to use for the connection
  database: DBI:SQLite:dbname=trend-tracker.sqlite3
  #
  # table:    mydata
  #      Names the table where the data is stored; useful if data is
  #      coming into multiple data sets.  If this isn't set, it's pulled
  #      from the incoming 'table' parameter.  If that is unset, it
  #      assumes "data" is right.
  table: mydata
  #
  # key: foo
  #      this field is used to determine if there is data for a given numeric
  #      slot.  EG, if the key is "foo" then the data collection engine will
  #      look for "foo0", "foo1", ... and will collect data until one is found
  #      to be empty.
  #
  key:         who
  #
  # parameters: name, supercool, gravity
  #      This collects the list of parameters to collect for each of the keys
  #      found.  For example, if the above three parameters are listed, then
  #      the data collection engine will look for name0, supercool0, gravity0,
  #      and so on, for each key found
  parameters:  favoritecolor, favoritefood, favoritedrink
  #
  # extras: dataversion, comment
  #      Contains a list of 'singular' extra values to be collected as well.
  #
  extras:      dataversion,surveyversion
  #
  # values: regexp
  #      This defines a regular expression that each of the parameters
  #      is allowed to match against.  If not set, then any value will
  #      be assumed to be ok.  Make sure to bound the expression by ^
  #      and $ if it must match exactly from beginning to end.
  values:      ^([a-zA-Z0-9 ])$
  keyvalues:   ^[a-zA-Z ])$
  extravalues: ^[0-9\.]+$
  #
  # noblanks: true
  #      If any of the above expressions fail, the default is to not
  #      collect that row of data at all.  However, if desired the bogus
  #      data can be replaced by an empty string and inserted.  Set
  #      allowblanks to '1' in order to make this happen.
  #
  allowblanks: false
  #
  # logaddress: sha1
  #      Either a 1 value to indicate logging the incoming connection address
  #      with the data, or a sha1 hash if you want to anonomize the data a bit
  #      before storing it
  logaddress:  sha1
  #startat:     0
  #
  # thankyounote: <h2>Thank you</h2> <p>so much for your submission!</p>
  #      If exits, this prints a thank you message for the data they submitted
  thankyounote: <h2>Thank you</h2> <p>so much for your submission!</p>
  #
  # thankyounotefile:  myfile.html
  #      If defined, this dumps the contents of the file to the output
  #      when a submission is received.  Note that the contents will be
  #      printed after the 'thankyounote' token contents.  Either, both
  #      or none of these two directives can be used.
  thankyounotefile:  myfile.html


=head1 INSTALLING

Typically this can be installed by simply copying it to the directory
it should serve and renaming it to I<index.cgi>
(e.g. I</var/www/my-server/download/index.cgi>) .  Make sure to make
it B<executable> and make sure to create a I<trend-watcher.config>
file for it to read.

You may need to set the I<ExecCGI> option in an apache I<.htaccess>
file or I<httpd.conf> file as well:

  Options +ExecCGI

In addition, if your server doesn't support the .cgi extension, make sure this
line is uncommented in your I<httpd.conf> file:

  AddHandler cgi-script .cgi

=head1 NOTES

If you care about the data and don't want the details exposed for any
reason, it's recommended that you use the I<include> directive and
place the main configuration file and database file outside the
web-accessible area.

This will likely only work with apache as the script expects the
SCRIPT_FILENAME environment variable to be set, which may be an
apache-ism.

=head1 SEE ALSO

createdb(1), trend-analysis(1)

=head1 TODO

* Finish (start) the analysis tool.

=head1 AUTHOR

Wes Hardaker E<lt>opensource AT hardakers DOT netE<gt>

=head1 COPYRIGHT and LICENSE

Copyright (c) 2012 Wes Hardaker

All rights reserved.  This program is free software; you may
redistribute it and/or modify it under the same terms as Perl itself.
