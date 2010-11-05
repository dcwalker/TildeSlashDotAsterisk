require 'rubygems'
require 'pp'
begin
  require 'wirble'

  # init wirble
  Wirble.init
  Wirble.colorize
rescue LoadError => err
  $stderr.puts "Couldn't load Wirble: #{err}"
end

# print SQL to STDOUT
if ENV.include?('RAILS_ENV') && !Object.const_defined?('RAILS_DEFAULT_LOGGER')
  require 'logger'
  RAILS_DEFAULT_LOGGER = Logger.new(STDOUT)
end